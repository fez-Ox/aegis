import 'package:flutter/material.dart';

import 'services/api_service.dart';
import 'services/call_service.dart';
import 'services/history_service.dart';
import 'services/preferences_service.dart';
import 'services/voice_service.dart';
import 'theme/app_theme.dart';
import 'views/caregiver_home.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  const baseUrl = String.fromEnvironment(
    'AEGIS_BASE_URL',
    defaultValue: ApiService.defaultBaseUrl,
  );
  runApp(AegisCaregiverApp(
    apiService: ApiService(baseUrl: baseUrl),
    voiceService: DeviceVoiceService(),
    historyService: HistoryService(),
    preferencesService: PreferencesService(),
    callService: DeviceCallService(),
  ));
}

class AegisCaregiverApp extends StatelessWidget {
  final ApiService apiService;
  final VoiceService voiceService;
  final HistoryService historyService;
  final PreferencesService preferencesService;
  final CallService callService;

  const AegisCaregiverApp({
    super.key,
    required this.apiService,
    required this.voiceService,
    required this.historyService,
    required this.preferencesService,
    required this.callService,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Aegis Caregiver',
      debugShowCheckedModeBanner: false,
      theme: PatientTheme.theme,
      home: CaregiverHome(
        apiService: apiService,
        voiceService: voiceService,
        historyService: historyService,
        preferencesService: preferencesService,
        callService: callService,
      ),
    );
  }
}
