import 'package:shared_preferences/shared_preferences.dart';

import '../models/patient_profile.dart';

/// Device-only settings. The caregiver phone number is collected on first run
/// and is never uploaded to Aegis memory.
class PreferencesService {
  /// The server address is device-only config. Empty means "use the build
  /// default" so a fresh install needs no setup to reach the deployed API.
  Future<String?> loadServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('server_url');
  }

  Future<void> saveServerUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_url', url.trim());
  }

  Future<PatientProfile> load() async {
    final prefs = await SharedPreferences.getInstance();
    return PatientProfile.fromPrefs({
      'patient_name': prefs.getString('patient_name') ?? '',
      'caregiver_name': prefs.getString('caregiver_name') ?? '',
      'caregiver_phone': prefs.getString('caregiver_phone') ?? '',
      'relationship': prefs.getString('relationship') ?? '',
    });
  }

  Future<PatientProfile> save(PatientProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    for (final entry in profile.toPrefs().entries) {
      await prefs.setString(entry.key, entry.value);
    }
    return profile;
  }
}
