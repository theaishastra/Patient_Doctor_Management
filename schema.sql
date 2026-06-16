-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Profiles Table (Base table for users linked to Supabase Auth)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'doctor', 'patient')),
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS for profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- 2. Doctors Table (Extends profiles)
CREATE TABLE IF NOT EXISTS public.doctors (
    id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    specialization TEXT,
    license_number TEXT,
    contact_number TEXT,
    bio TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS for doctors
ALTER TABLE public.doctors ENABLE ROW LEVEL SECURITY;

-- 3. Patients Table (Extends profiles)
CREATE TABLE IF NOT EXISTS public.patients (
    id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    date_of_birth DATE,
    gender TEXT,
    blood_group TEXT,
    contact_number TEXT,
    emergency_contact TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS for patients
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;

-- 4. Doctor-Patient Assignments (Many-to-Many relationship)
CREATE TABLE IF NOT EXISTS public.assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id UUID NOT NULL REFERENCES public.doctors(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES public.patients(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(doctor_id, patient_id)
);

-- Enable RLS for assignments
ALTER TABLE public.assignments ENABLE ROW LEVEL SECURITY;

-- 5. Treatments Table
CREATE TABLE IF NOT EXISTS public.treatments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES public.patients(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES public.doctors(id) ON DELETE CASCADE,
    diagnosis TEXT NOT NULL,
    treatment_plan TEXT NOT NULL,
    suggested_medicines TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS for treatments
ALTER TABLE public.treatments ENABLE ROW LEVEL SECURITY;

-- 6. Medical Documents Table
CREATE TABLE IF NOT EXISTS public.medical_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES public.patients(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL, -- Path inside the supabase storage bucket
    file_url TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT
);

-- Enable RLS for medical documents
ALTER TABLE public.medical_documents ENABLE ROW LEVEL SECURITY;

-- 7. Activity Logs Table (Audit trail)
CREATE TABLE IF NOT EXISTS public.activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    user_name TEXT,
    role TEXT,
    action TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS for activity logs
ALTER TABLE public.activity_logs ENABLE ROW LEVEL SECURITY;

-- 8. Chat Messages Table
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES public.assignments(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    sender_role TEXT NOT NULL CHECK (sender_role IN ('doctor', 'patient', 'admin')),
    message_type TEXT NOT NULL CHECK (message_type IN ('text', 'image', 'video', 'audio', 'file')),
    content TEXT,
    file_path TEXT,
    file_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chat_messages_content_check CHECK (
        (message_type = 'text' AND content IS NOT NULL AND file_path IS NULL)
        OR (message_type != 'text' AND file_path IS NOT NULL AND file_name IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_assignment_id ON public.chat_messages(assignment_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON public.chat_messages(created_at);

-- Enable RLS for chat messages
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;


-- =========================================================================
-- TRIGGERS FOR USER REGISTRATION
-- =========================================================================

-- Trigger function to automatically insert new auth.users into profiles, doctors, and patients
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
DECLARE
    user_role TEXT;
    user_full_name TEXT;
BEGIN
    user_role := COALESCE(new.raw_user_meta_data->>'role', 'patient');
    user_full_name := COALESCE(new.raw_user_meta_data->>'full_name', 'Unnamed User');

    -- Insert into public.profiles
    INSERT INTO public.profiles (id, role, full_name, email)
    VALUES (new.id, user_role, user_full_name, new.email);

    -- Insert role-specific profile details
    IF user_role = 'doctor' THEN
        INSERT INTO public.doctors (id, specialization, license_number, contact_number, bio)
        VALUES (new.id, NULL, NULL, NULL, NULL);
    ELSIF user_role = 'patient' THEN
        INSERT INTO public.patients (id, date_of_birth, gender, blood_group, contact_number, emergency_contact)
        VALUES (new.id, NULL, NULL, NULL, NULL, NULL);
    END IF;

    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create the trigger
CREATE OR REPLACE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- =========================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =========================================================================

-- 1. Profiles Policies
DROP POLICY IF EXISTS "Users can view all profiles (needed for lookups)" ON public.profiles;
CREATE POLICY "Users can view all profiles (needed for lookups)" ON public.profiles
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile" ON public.profiles
    FOR UPDATE TO authenticated USING (auth.uid() = id);

-- 2. Doctors Policies
DROP POLICY IF EXISTS "Anyone authenticated can view active doctors" ON public.doctors;
CREATE POLICY "Anyone authenticated can view active doctors" ON public.doctors
    FOR SELECT TO authenticated USING (is_active = true);

DROP POLICY IF EXISTS "Doctors can update their own info" ON public.doctors;
CREATE POLICY "Doctors can update their own info" ON public.doctors
    FOR UPDATE TO authenticated USING (auth.uid() = id);

-- 3. Patients Policies
DROP POLICY IF EXISTS "Patients can view/update their own info" ON public.patients;
CREATE POLICY "Patients can view/update their own info" ON public.patients
    FOR ALL TO authenticated USING (auth.uid() = id OR EXISTS (
        -- Or an assigned doctor can view it
        SELECT 1 FROM public.assignments a
        WHERE a.doctor_id = auth.uid() AND a.patient_id = public.patients.id
    ));

-- 4. Assignments Policies
DROP POLICY IF EXISTS "Admins can manage assignments" ON public.assignments;
CREATE POLICY "Admins can manage assignments" ON public.assignments
    FOR ALL TO authenticated USING (
        EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
    );

DROP POLICY IF EXISTS "Users can view their assignments" ON public.assignments;
CREATE POLICY "Users can view their assignments" ON public.assignments
    FOR SELECT TO authenticated USING (
        auth.uid() = doctor_id OR auth.uid() = patient_id
    );

-- 5. Treatments Policies
DROP POLICY IF EXISTS "Doctors can manage treatments" ON public.treatments;
CREATE POLICY "Doctors can manage treatments" ON public.treatments
    FOR ALL TO authenticated USING (
        auth.uid() = doctor_id
    );

DROP POLICY IF EXISTS "Patients can view their own treatments" ON public.treatments;
CREATE POLICY "Patients can view their own treatments" ON public.treatments
    FOR SELECT TO authenticated USING (
        auth.uid() = patient_id
    );

-- 6. Medical Documents Policies
DROP POLICY IF EXISTS "Patients can manage their own documents" ON public.medical_documents;
CREATE POLICY "Patients can manage their own documents" ON public.medical_documents
    FOR ALL TO authenticated USING (
        auth.uid() = patient_id
    );

DROP POLICY IF EXISTS "Assigned doctors can view patient documents" ON public.medical_documents;
CREATE POLICY "Assigned doctors can view patient documents" ON public.medical_documents
    FOR SELECT TO authenticated USING (
        EXISTS (
            SELECT 1 FROM public.assignments a
            WHERE a.doctor_id = auth.uid() AND a.patient_id = public.medical_documents.patient_id
        )
    );

-- 7. Activity Logs Policies
DROP POLICY IF EXISTS "Only admins can view activity logs" ON public.activity_logs;
CREATE POLICY "Only admins can view activity logs" ON public.activity_logs
    FOR SELECT TO authenticated USING (
        EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
    );

DROP POLICY IF EXISTS "Allow system logging" ON public.activity_logs;
CREATE POLICY "Allow system logging" ON public.activity_logs
    FOR INSERT TO authenticated WITH CHECK (true);

-- 8. Chat Messages Policies
DROP POLICY IF EXISTS "Assignment members can view chat messages" ON public.chat_messages;
CREATE POLICY "Assignment members can view chat messages" ON public.chat_messages
    FOR SELECT TO authenticated USING (
        EXISTS (
            SELECT 1 FROM public.assignments a
            WHERE a.id = chat_messages.assignment_id
            AND (a.doctor_id = auth.uid() OR a.patient_id = auth.uid())
        )
        OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
    );

DROP POLICY IF EXISTS "Assignment members can send chat messages" ON public.chat_messages;
CREATE POLICY "Assignment members can send chat messages" ON public.chat_messages
    FOR INSERT TO authenticated WITH CHECK (
        sender_id = auth.uid()
        AND (
            EXISTS (
                SELECT 1 FROM public.assignments a
                WHERE a.id = chat_messages.assignment_id
                AND (a.doctor_id = auth.uid() OR a.patient_id = auth.uid())
            )
            OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
        )
    );

DROP POLICY IF EXISTS "Admins can manage all chat messages" ON public.chat_messages;
CREATE POLICY "Admins can manage all chat messages" ON public.chat_messages
    FOR ALL TO authenticated USING (
        EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
    );
