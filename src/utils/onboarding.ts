export type SavedDepartment = 'men' | 'women';

export interface OnboardingProfile {
  completed: true;
  name: string;
  preferredSize: string | null;
  department: SavedDepartment | null;
}

const ONBOARDING_STORAGE_KEY = 'dhaaga_onboarding_profile_v1';

export function getOnboardingProfile(): OnboardingProfile | null {
  try {
    const raw = localStorage.getItem(ONBOARDING_STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<OnboardingProfile>;
    if (value.completed !== true) return null;
    const department = value.department === 'men' || value.department === 'women'
      ? value.department
      : null;
    return {
      completed: true,
      name: typeof value.name === 'string' && value.name.trim() ? value.name.trim() : 'Meera',
      preferredSize: typeof value.preferredSize === 'string' && value.preferredSize.trim()
        ? value.preferredSize.trim()
        : null,
      department,
    };
  } catch {
    return null;
  }
}

export function saveOnboardingProfile(profile: Omit<OnboardingProfile, 'completed'>): void {
  try {
    localStorage.setItem(
      ONBOARDING_STORAGE_KEY,
      JSON.stringify({ ...profile, completed: true }),
    );
  } catch {
    // The app still works for this tab when browser storage is unavailable.
  }
}
