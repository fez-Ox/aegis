import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/dataset_info.dart';
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
      backgroundColor: AppTheme.darkCanvas,
      appBar: AppBar(
        backgroundColor: AppTheme.darkCanvas,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        title: Row(
          children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                color: AppTheme.primaryTeal.withOpacity(0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.shield_rounded, color: AppTheme.primaryTeal, size: 22),
            ),
            const SizedBox(width: 10),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  "AEGIS",
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.8,
                    color: AppTheme.textHighContrast,
                  ),
                ),
                Text(
                  "Spatial Memory Care",
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                    color: AppTheme.textMuted,
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          _buildIosBarAction(
            icon: Icons.video_library_rounded,
            tooltip: "Switch Video / Dataset",
            color: AppTheme.royalAmethyst,
            onPressed: _showDatasetSelectorSheet,
          ),
          const SizedBox(width: 6),
          _buildIosBarAction(
            icon: Icons.science_outlined,
            tooltip: "Simulate Spatial Transition",
            color: AppTheme.primaryTeal,
            onPressed: _showSimulationSheet,
          ),
          const SizedBox(width: 6),
          _buildIosBarAction(
            icon: Icons.settings_outlined,
            tooltip: "Server Settings",
            color: AppTheme.textMuted,
            onPressed: _showSettingsDialog,
          ),
          const SizedBox(width: 16),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(56),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            child: Container(
              height: 44,
              padding: const EdgeInsets.all(3),
              decoration: BoxDecoration(
                color: AppTheme.segmentedTrack,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: _buildModeTab(
                      title: "Patient Recall",
                      icon: Icons.person_rounded,
                      isSelected: _selectedModeIndex == 0,
                      onTap: () {
                        HapticFeedback.selectionClick();
                        setState(() => _selectedModeIndex = 0);
                      },
                    ),
                  ),
                  Expanded(
                    child: _buildModeTab(
                      title: "Caregiver Audit",
                      icon: Icons.monitor_heart_rounded,
                      isSelected: _selectedModeIndex == 1,
                      onTap: () {
                        HapticFeedback.selectionClick();
                        setState(() => _selectedModeIndex = 1);
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      body: IndexedStack(
        key: ValueKey('${widget.apiService.activeDatasetId}_$_selectedModeIndex'),
        index: _selectedModeIndex,
        children: [
          PatientView(
            key: ValueKey('patient_${widget.apiService.activeDatasetId}'),
            apiService: widget.apiService,
          ),
          CaregiverView(
            key: ValueKey('caregiver_${widget.apiService.activeDatasetId}'),
            apiService: widget.apiService,
          ),
        ],
      ),
    );
  }


  Widget _buildIosBarAction({
    required IconData icon,
    required String tooltip,
    required Color color,
    required VoidCallback onPressed,
  }) {
    return SizedBox(
      width: 40,
      height: 40,
      child: IconButton(
        padding: EdgeInsets.zero,
        constraints: const BoxConstraints(minWidth: 40, minHeight: 40),
        icon: Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: color.withOpacity(0.08),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: color, size: 20),
        ),
        tooltip: tooltip,
        onPressed: onPressed,
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
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeInOut,
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.segmentedThumb : Colors.transparent,
          borderRadius: BorderRadius.circular(9),
          boxShadow: isSelected
              ? const [
                  BoxShadow(
                    color: Color(0x18000000),
                    blurRadius: 4,
                    offset: Offset(0, 1.5),
                  ),
                ]
              : null,
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 16,
              color: isSelected ? AppTheme.primaryTeal : AppTheme.textMuted,
            ),
            const SizedBox(width: 6),
            Text(
              title,
              style: TextStyle(
                fontSize: 14,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                color: isSelected ? AppTheme.textHighContrast : AppTheme.textMuted,
                letterSpacing: -0.2,
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
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: AppTheme.cardBorder, width: 0.8),
        ),
        titlePadding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
        contentPadding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
        actionsPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        title: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: AppTheme.systemBlue.withOpacity(0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.wifi_rounded, color: AppTheme.systemBlue, size: 20),
            ),
            const SizedBox(width: 12),
            const Text(
              "Backend Connection",
              style: TextStyle(
                color: AppTheme.textHighContrast,
                fontSize: 18,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.3,
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
              style: TextStyle(color: AppTheme.textMuted, fontSize: 13, height: 1.4),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: controller,
              style: const TextStyle(
                color: AppTheme.textHighContrast,
                fontSize: 15,
                fontWeight: FontWeight.w500,
              ),
              decoration: InputDecoration(
                filled: true,
                fillColor: AppTheme.darkCanvas,
                hintText: "http://192.168.1.XX:8000",
                hintStyle: const TextStyle(color: AppTheme.tertiaryLabel, fontSize: 14),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.cardBorder, width: 0.8),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.cardBorder, width: 0.8),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppTheme.primaryTeal, width: 1.5),
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              ),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.darkCanvas,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Row(
                children: [
                  Icon(Icons.info_outline_rounded, size: 14, color: AppTheme.textMuted),
                  SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      "Default LAN: 0.0.0.0:8000 | Emulator: 10.0.2.2:8000",
                      style: TextStyle(color: AppTheme.textMuted, fontSize: 11),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            ),
            child: const Text(
              "Cancel",
              style: TextStyle(color: AppTheme.textMuted, fontWeight: FontWeight.w600),
            ),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryTeal,
              foregroundColor: Colors.white,
              elevation: 0,
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: () async {
              widget.apiService.updateBaseUrl(controller.text);
              final ok = await widget.apiService.checkHealth();
              if (mounted) {
                Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    behavior: SnackBarBehavior.floating,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
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
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  void _showDatasetSelectorSheet() async {
    final datasets = await widget.apiService.fetchDatasets();
    if (!mounted) return;

    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.darkSurface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // iOS Grabber Handle
              Center(
                child: Container(
                  width: 36,
                  height: 5,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: AppTheme.cardBorder,
                    borderRadius: BorderRadius.circular(2.5),
                  ),
                ),
              ),
              Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: AppTheme.royalAmethyst.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.video_library_rounded, color: AppTheme.royalAmethyst, size: 20),
                  ),
                  const SizedBox(width: 12),
                  const Text(
                    "Switch Video Scene Graph",
                    style: TextStyle(
                      color: AppTheme.textHighContrast,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.3,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                "Select any evaluated video in the repository to load its 3D Scene Graph, Caregiver Audit, and Patient Recall artifacts.",
                style: TextStyle(color: AppTheme.textMuted, fontSize: 13, height: 1.4),
              ),
              const SizedBox(height: 16),
              ...datasets.map((d) {
                final isCurrent = d.datasetId == (widget.apiService.activeDatasetId ?? 'demo01');
                return _buildDatasetTile(
                  dataset: d,
                  isSelected: isCurrent,
                  onTap: () async {
                    HapticFeedback.selectionClick();
                    Navigator.pop(ctx);
                    await widget.apiService.selectDataset(d.datasetId);
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          behavior: SnackBarBehavior.floating,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          backgroundColor: const Color(0xFF0F766E),
                          content: Text("✓ Active video switched to ${d.datasetId} (${d.title})"),
                        ),
                      );
                      setState(() {});
                    }
                  },
                );
              }),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDatasetTile({
    required DatasetInfo dataset,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: isSelected ? AppTheme.royalAmethyst.withOpacity(0.08) : AppTheme.darkCanvas,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isSelected ? AppTheme.royalAmethyst : AppTheme.cardBorder,
          width: isSelected ? 1.8 : 0.8,
        ),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: (isSelected ? AppTheme.royalAmethyst : AppTheme.primaryTeal).withOpacity(0.14),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      dataset.datasetId,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: isSelected ? AppTheme.royalAmethyst : AppTheme.primaryTeal,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      dataset.title,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textHighContrast,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  if (isSelected)
                    const Icon(Icons.check_circle_rounded, color: AppTheme.royalAmethyst, size: 20),
                ],
              ),
              const SizedBox(height: 8),
              if (dataset.anchors.isNotEmpty)
                Text(
                  "Anchors: ${dataset.anchors.join(', ')}",
                  style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
                ),
              if (dataset.trackedObjects.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(
                    "Tracked: ${dataset.trackedObjects.take(3).join(', ')}${dataset.trackedObjects.length > 3 ? ' +${dataset.trackedObjects.length - 3} more' : ''}",
                    style: const TextStyle(fontSize: 11, color: AppTheme.tealAccent),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  void _showSimulationSheet() {
    final activeId = (widget.apiService.activeDatasetId ?? 'demo01').toLowerCase();
    final isKitchen = activeId.contains('demo03') || activeId.contains('kitchen') || activeId.contains('fridge');
    final isOffice = activeId.contains('demo06') || activeId.contains('self') || activeId.contains('desk');

    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.darkSurface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // iOS Grabber Handle
              Center(
                child: Container(
                  width: 36,
                  height: 5,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: AppTheme.cardBorder,
                    borderRadius: BorderRadius.circular(2.5),
                  ),
                ),
              ),
              Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: AppTheme.primaryTeal.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.science_outlined, color: AppTheme.primaryTeal, size: 20),
                  ),
                  const SizedBox(width: 12),
                  const Text(
                    "Spatial Transition Simulator",
                    style: TextStyle(
                      color: AppTheme.textHighContrast,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.3,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                "Inject live spatial state shifts into R4DSG memory for [$activeId] to demonstrate real-time reasoning and caregiver alerts.",
                style: const TextStyle(color: AppTheme.textMuted, fontSize: 13, height: 1.4),
              ),
              const SizedBox(height: 18),
              if (isOffice) ...[
                _buildSimTile(
                  title: "Bottle on Desk 1",
                  subtitle: "Resting actively on primary desk",
                  icon: Icons.table_restaurant_rounded,
                  color: AppTheme.tealAccent,
                  onTap: () => _triggerSim(ctx, "bottle_table1", "Bottle placed on Desk 1"),
                ),
                _buildSimTile(
                  title: "Bottle Occluded",
                  subtitle: "Triggers Occlusion & Spatial Permanence",
                  icon: Icons.visibility_off_rounded,
                  color: AppTheme.royalAmethyst,
                  onTap: () => _triggerSim(ctx, "bottle_occluded", "Bottle occluded behind monitor"),
                ),
                _buildSimTile(
                  title: "Bottle on Desk 2",
                  subtitle: "Triggers Relocation Memory Transition",
                  icon: Icons.desk_rounded,
                  color: AppTheme.alertAmber,
                  onTap: () => _triggerSim(ctx, "bottle_table2", "Bottle relocated to Desk 2"),
                ),
              ] else if (isKitchen) ...[
                _buildSimTile(
                  title: "Cooking Pot on Sink",
                  subtitle: "Resting on Sink counter surface",
                  icon: Icons.soup_kitchen_rounded,
                  color: AppTheme.tealAccent,
                  onTap: () => _triggerSim(ctx, "floor", "Cooking Pot placed near Sink"),
                ),
                _buildSimTile(
                  title: "Hold Pot in Hands",
                  subtitle: "Triggers In-Hand Kinematic Tracking",
                  icon: Icons.pan_tool_rounded,
                  color: AppTheme.systemIndigo,
                  onTap: () => _triggerSim(ctx, "in_hand", "Cooking Pot picked up by user"),
                ),
                _buildSimTile(
                  title: "Store Pot in Refrigerator",
                  subtitle: "Triggers Occlusion & Enclosure Persistence",
                  icon: Icons.kitchen_rounded,
                  color: AppTheme.systemGreen,
                  onTap: () => _triggerSim(ctx, "cabinet", "Cooking Pot placed in Refrigerator"),
                ),
              ] else ...[
                _buildSimTile(
                  title: "Move Object to Floor",
                  subtitle: "Triggers Caregiver Displaced Item Alert",
                  icon: Icons.warning_amber_rounded,
                  color: AppTheme.alertAmber,
                  onTap: () => _triggerSim(ctx, "floor", "Object moved to floor"),
                ),
                _buildSimTile(
                  title: "Pick up Object in Hand",
                  subtitle: "Triggers In-Hand Kinematic Tracking",
                  icon: Icons.pan_tool_rounded,
                  color: AppTheme.systemIndigo,
                  onTap: () => _triggerSim(ctx, "in_hand", "Object picked up by user"),
                ),
                _buildSimTile(
                  title: "Store in Room Anchor",
                  subtitle: "Triggers Occlusion & Spatial Permanence",
                  icon: Icons.inventory_2_rounded,
                  color: AppTheme.systemGreen,
                  onTap: () => _triggerSim(ctx, "cabinet", "Object safely stored in anchor"),
                ),
              ],
              const Divider(color: AppTheme.cardBorder, height: 20),
              TextButton.icon(
                icon: const Icon(Icons.refresh_rounded, color: AppTheme.textMuted, size: 18),
                label: const Text(
                  "Reset Memory Graph to Baseline",
                  style: TextStyle(color: AppTheme.textMuted, fontWeight: FontWeight.w600, fontSize: 13),
                ),
                style: TextButton.styleFrom(
                  minimumSize: const Size.fromHeight(44),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: () async {
                  Navigator.pop(ctx);
                  await widget.apiService.resetMemory();
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        behavior: SnackBarBehavior.floating,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        content: const Text("Memory graph reset to baseline."),
                      ),
                    );
                    setState(() {});
                  }
                },
              ),
            ],
          ),
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
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: () {
          HapticFeedback.lightImpact();
          onTap();
        },
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: color.withOpacity(0.06),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: color.withOpacity(0.25), width: 0.8),
          ),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        color: color,
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(color: AppTheme.textMuted, fontSize: 12),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: color.withOpacity(0.6), size: 20),
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
