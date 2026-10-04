import 'package:flutter/material.dart';
import 'services/api_service.dart';
import 'theme/app_theme.dart';
import 'views/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final apiService = ApiService();
  runApp(AegisApp(apiService: apiService));
}

class AegisApp extends StatelessWidget {
  final ApiService apiService;

  const AegisApp({super.key, required this.apiService});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Aegis Memory',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: HomeScreen(apiService: apiService),
    );
  }
}
