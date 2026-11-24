import 'package:flutter/material.dart';

import 'services/api_service.dart';
import 'services/call_service.dart';
import 'services/preferences_service.dart';
import 'services/voice_service.dart';
import 'theme/app_theme.dart';
import 'views/patient_home.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Deployed FastAPI (Modal) by default: works on cellular/Wi-Fi with no USB.
  // Override at build time for a local server, or from inside the app.
  const baseUrl = String.fromEnvironment(
    'AEGIS_BASE_URL',
    defaultValue: ApiService.defaultBaseUrl,
  );
  runApp(AegisPatientApp(
    apiService: ApiService(baseUrl: baseUrl),
    voiceService: DeviceVoiceService(),
    callService: DeviceCallService(),
    preferencesService: PreferencesService(),
  ));
}

/// Patient-only entrypoint. The caregiver app lives in a separate folder and
/// will get its own entrypoint; SharedPreferences are namespaced per app ID.
class AegisPatientApp extends StatelessWidget {
  final ApiService apiService;
  final VoiceService voiceService;
  final CallService callService;
  final PreferencesService preferencesService;

  const AegisPatientApp({
    super.key,
    required this.apiService,
    required this.voiceService,
    required this.callService,
    required this.preferencesService,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Aegis Patient',
      debugShowCheckedModeBanner: false,
      theme: PatientTheme.theme,
      home: PatientHome(
        apiService: apiService,
        voiceService: voiceService,
        callService: callService,
        preferencesService: preferencesService,
      ),
    );
  }
}
