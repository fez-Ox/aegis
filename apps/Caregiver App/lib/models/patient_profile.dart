/// Locally stored configuration for the patient app.
///
/// The caregiver phone number is mandatory: it is collected the first time the
/// app is opened and can be changed later from the call screen. Nothing is sent
/// to Aegis memory — this is device-only data.
class PatientProfile {
  static const defaultPatientName = 'Arthur';
  static const defaultCaregiverName = 'Sarah';
  static const defaultRelationship = 'Your daughter · Caretaker';

  final String patientName;
  final String caregiverName;
  final String caregiverPhone;
  final String relationship;

  const PatientProfile({
    this.patientName = defaultPatientName,
    this.caregiverName = defaultCaregiverName,
    this.caregiverPhone = '',
    this.relationship = defaultRelationship,
  });

  /// The call feature is unusable until a number has been set once.
  bool get isConfigured => caregiverPhone.trim().isNotEmpty;

  PatientProfile copyWith({
    String? patientName,
    String? caregiverName,
    String? caregiverPhone,
    String? relationship,
  }) {
    return PatientProfile(
      patientName: patientName ?? this.patientName,
      caregiverName: caregiverName ?? this.caregiverName,
      caregiverPhone: caregiverPhone ?? this.caregiverPhone,
      relationship: relationship ?? this.relationship,
    );
  }

  Map<String, String> toPrefs() => {
        'patient_name': patientName,
        'caregiver_name': caregiverName,
        'caregiver_phone': caregiverPhone,
        'relationship': relationship,
        'onboarding_complete': isConfigured ? 'true' : 'false',
      };

  factory PatientProfile.fromPrefs(Map<String, String> prefs) {
    return PatientProfile(
      patientName: prefs['patient_name'] ?? defaultPatientName,
      caregiverName: prefs['caregiver_name'] ?? defaultCaregiverName,
      caregiverPhone: prefs['caregiver_phone'] ?? '',
      relationship: prefs['relationship'] ?? defaultRelationship,
    );
  }
}
