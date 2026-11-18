import 'package:flutter/material.dart';

import 'services/api_service.dart';
import 'theme/app_theme.dart';
import 'views/ask_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  const baseUrl = String.fromEnvironment(
    'AEGIS_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );
  runApp(AegisApp(apiService: ApiService(baseUrl: baseUrl)));
}

/// The app only asks questions and displays answers. No tracking, simulation,
/// capture control, or dataset management lives here.
class AegisApp extends StatelessWidget {
  final ApiService apiService;

  const AegisApp({super.key, required this.apiService});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Aegis Memory',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: AskScreen(apiService: apiService),
    );
  }
}
