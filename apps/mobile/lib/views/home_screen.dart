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
        actions: [
          IconButton(
            icon: const Icon(Icons.science_outlined, color: AppTheme.tealAccent),
            tooltip: "Simulate Spatial Transition",
            onPressed: _showSimulationSheet,
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined, color: AppTheme.textMuted),
            tooltip: "Server Settings",
            onPressed: _showSettingsDialog,
          ),
          const SizedBox(width: 8),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(60),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            child: Container(
              height: 48,
              decoration: BoxDecoration(
                color: AppTheme.darkSurface,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppTheme.cardBorder, width: 1.5),
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

  void _showSettingsDialog() {
    final controller = TextEditingController(text: widget.apiService.baseUrl);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.darkSurface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: AppTheme.cardBorder),
        ),
        title: const Row(
          children: [
            Icon(Icons.wifi_rounded, color: AppTheme.tealAccent),
            SizedBox(width: 10),
            Text(
              "Backend Connection",
              style: TextStyle(
                color: AppTheme.textHighContrast,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "Enter the IP address of your host machine running run_server.py:",
              style: TextStyle(color: AppTheme.textMuted, fontSize: 14),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              style: const TextStyle(color: AppTheme.textHighContrast),
              decoration: InputDecoration(
                filled: true,
                fillColor: AppTheme.darkCanvas,
                hintText: "http://192.168.1.XX:8000",
                hintStyle: const TextStyle(color: AppTheme.textMuted),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.cardBorder),
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              "Default LAN: 0.0.0.0:8000 | Emulator: 10.0.2.2:8000",
              style: TextStyle(color: AppTheme.textMuted, fontSize: 12),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text("Cancel", style: TextStyle(color: AppTheme.textMuted)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryTeal,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: () async {
              widget.apiService.updateBaseUrl(controller.text);
              final ok = await widget.apiService.checkHealth();
              if (mounted) {
                Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    backgroundColor: ok ? const Color(0xFF065F46) : const Color(0xFF991B1B),
                    content: Text(
                      ok
                          ? "✓ Connected to Aegis Backend (${widget.apiService.baseUrl})"
                          : "⚠️ Connection failed. Using offline fallback.",
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                    ),
                  ),
                );
              }
            },
            child: const Text(
              "Save & Connect",
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  void _showSimulationSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.darkSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Row(
              children: [
                Icon(Icons.science_outlined, color: AppTheme.tealAccent, size: 24),
                SizedBox(width: 10),
                Text(
                  "Spatial Transition Simulator",
                  style: TextStyle(
                    color: AppTheme.textHighContrast,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              "Inject live spatial state shifts into R4DSG memory to demonstrate real-time reasoning and caregiver alerts.",
              style: TextStyle(color: AppTheme.textMuted, fontSize: 13),
            ),
            const SizedBox(height: 18),
            _buildSimTile(
              title: "Move Shoes to Floor",
              subtitle: "Triggers Caregiver Displaced Item Alert",
              icon: Icons.warning_amber_rounded,
              color: AppTheme.alertAmber,
              onTap: () => _triggerSim(ctx, "floor", "Shoes #1 moved to floor"),
            ),
            _buildSimTile(
              title: "Pick up Shoes in Hand",
              subtitle: "Triggers In-Hand Kinematic Tracking",
              icon: Icons.pan_tool_rounded,
              color: AppTheme.royalAmethyst,
              onTap: () => _triggerSim(ctx, "in_hand", "Shoes #1 picked up by user"),
            ),
            _buildSimTile(
              title: "Store Shoes in Cabinet",
              subtitle: "Triggers Occlusion & Spatial Permanence",
              icon: Icons.inventory_2_rounded,
              color: AppTheme.tealAccent,
              onTap: () => _triggerSim(ctx, "cabinet", "Shoes #1 safely placed in cabinet"),
            ),
            const Divider(color: AppTheme.cardBorder, height: 24),
            TextButton.icon(
              icon: const Icon(Icons.refresh_rounded, color: AppTheme.textMuted, size: 18),
              label: const Text(
                "Reset Memory Graph to Baseline",
                style: TextStyle(color: AppTheme.textMuted),
              ),
              onPressed: () async {
                Navigator.pop(ctx);
                await widget.apiService.resetMemory();
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("Memory graph reset to baseline.")),
                  );
                  setState(() {});
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSimTile({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: color.withOpacity(0.08),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: color.withOpacity(0.3)),
          ),
          child: Row(
            children: [
              Icon(icon, color: color, size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        color: color,
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                    Text(
                      subtitle,
                      style: const TextStyle(color: AppTheme.textMuted, fontSize: 12),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: color, size: 20),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _triggerSim(BuildContext ctx, String preset, String label) async {
    Navigator.pop(ctx);
    final ok = await widget.apiService.simulatePreset(preset);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: ok ? const Color(0xFF0F766E) : const Color(0xFF991B1B),
          content: Text(ok ? "✓ $label (Memory updated)" : "Simulation request failed"),
        ),
      );
      setState(() {});
    }
  }
}
