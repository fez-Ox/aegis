import 'package:flutter/material.dart';
import '../../models/timeline_event.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';

class CaregiverView extends StatefulWidget {
  final ApiService apiService;

  const CaregiverView({super.key, required this.apiService});

  @override
  State<CaregiverView> createState() => _CaregiverViewState();
}

class _CaregiverViewState extends State<CaregiverView> {
  List<TimelineEvent> _events = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadTimeline();
  }

  Future<void> _loadTimeline() async {
    setState(() => _isLoading = true);
    final events = await widget.apiService.fetchTimeline();
    setState(() {
      _events = events;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _loadTimeline,
      color: AppTheme.tealAccent,
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Caregiver Overview Header Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.darkSurface,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFF334155), width: 1.5),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.shield_outlined, color: AppTheme.tealAccent, size: 24),
                      SizedBox(width: 10),
                      Text(
                        "Caregiver Spatial Audit",
                        style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.textHighContrast),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    "Real-time spatio-temporal tracking across monitored home anchors.",
                    style: TextStyle(fontSize: 15, color: AppTheme.textMuted),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      _buildMetricTile("1 Active Anchor", "Storage Cabinet #1", AppTheme.royalAmethyst),
                      const SizedBox(width: 12),
                      _buildMetricTile("4 Instances", "Shoes #1, #2, #3, #4", AppTheme.tealAccent),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // Displaced Item Warning Card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.alertAmber.withOpacity(0.12),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.alertAmber, width: 1.5),
              ),
              child: const Row(
                children: [
                  Icon(Icons.info_outline_rounded, color: AppTheme.alertAmber, size: 24),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      "All tracked items are safely inside their designated room anchors.",
                      style: TextStyle(color: Color(0xFFFDE68A), fontSize: 14, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Timeline Header
            const Row(
              children: [
                Icon(Icons.timeline_rounded, color: AppTheme.tealAccent, size: 20),
                SizedBox(width: 8),
                Text(
                  "Activity History Log",
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.textHighContrast),
                ),
              ],
            ),
            const SizedBox(height: 14),

            if (_isLoading)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: CircularProgressIndicator(color: AppTheme.tealAccent),
                ),
              )
            else if (_events.isEmpty)
              const Center(child: Text("No events recorded today.", style: TextStyle(color: AppTheme.textMuted)))
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _events.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  final ev = _events[index];
                  return Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppTheme.darkSurface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: const Color(0xFF334155), width: 1),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: AppTheme.royalAmethyst.withOpacity(0.2),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.arrow_forward_rounded, color: Color(0xFFA5B4FC), size: 16),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                ev.summary,
                                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: AppTheme.textHighContrast),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                "Window: ${ev.startTime.toStringAsFixed(1)}s - ${ev.endTime.toStringAsFixed(1)}s",
                                style: const TextStyle(fontSize: 13, color: AppTheme.textMuted),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricTile(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.4), width: 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(color: AppTheme.textHighContrast, fontSize: 14, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}
