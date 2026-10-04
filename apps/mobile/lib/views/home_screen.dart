import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'caregiver/caregiver_view.dart';
import 'patient/patient_view.dart';

class HomeScreen extends StatefulWidget {
  final ApiService apiService;

  const HomeScreen({super.key, required this.apiService});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedModeIndex = 0; // 0 = Patient Mode, 1 = Caregiver Mode

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: AppTheme.darkCanvas,
        elevation: 0,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.primaryTeal.withOpacity(0.2),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.shield_rounded, color: AppTheme.tealAccent, size: 24),
            ),
            const SizedBox(width: 12),
            const Text(
              "AEGIS",
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w900,
                letterSpacing: 1.5,
                color: AppTheme.textHighContrast,
              ),
            ),
          ],
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(60),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            child: Container(
              height: 48,
              decoration: BoxDecoration(
                color: AppTheme.darkSurface,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: const Color(0xFF334155), width: 1.5),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: _buildModeTab(
                      title: "Patient Recall",
                      icon: Icons.person_rounded,
                      isSelected: _selectedModeIndex == 0,
                      onTap: () => setState(() => _selectedModeIndex = 0),
                    ),
                  ),
                  Expanded(
                    child: _buildModeTab(
                      title: "Caregiver Audit",
                      icon: Icons.monitor_heart_rounded,
                      isSelected: _selectedModeIndex == 1,
                      onTap: () => setState(() => _selectedModeIndex = 1),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      body: IndexedStack(
        index: _selectedModeIndex,
        children: [
          PatientView(apiService: widget.apiService),
          CaregiverView(apiService: widget.apiService),
        ],
      ),
    );
  }

  Widget _buildModeTab({
    required String title,
    required IconData icon,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primaryTeal : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 18, color: isSelected ? Colors.white : AppTheme.textMuted),
            const SizedBox(width: 6),
            Text(
              title,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: isSelected ? Colors.white : AppTheme.textMuted,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
