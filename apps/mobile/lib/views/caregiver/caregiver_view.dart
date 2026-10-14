import 'package:flutter/material.dart';
import '../../models/timeline_event.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';

class CaregiverView extends StatefulWidget {
  final ApiService apiService;
  final VoidCallback? onSwitchDataset;

  const CaregiverView({
    super.key,
    required this.apiService,
    this.onSwitchDataset,
  });

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
      color: AppTheme.primaryTeal,
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Caregiver Overview Header Card (Apple Inset Card)
            Container(
              padding: const EdgeInsets.all(18),
              decoration: AppTheme.iosCardDecoration(radius: 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 36,
                        height: 36,
                        decoration: BoxDecoration(
                          color: AppTheme.primaryTeal.withOpacity(0.12),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.shield_outlined, color: AppTheme.primaryTeal, size: 20),
                      ),
                      const SizedBox(width: 10),
                      const Expanded(
                        child: Text(
                          "Caregiver Spatial Audit",
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                            letterSpacing: -0.3,
                            color: AppTheme.textHighContrast,
                          ),
                        ),
                      ),
                      GestureDetector(
                        onTap: widget.onSwitchDataset,
                        behavior: HitTestBehavior.opaque,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: AppTheme.royalAmethyst.withOpacity(0.14),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppTheme.royalAmethyst.withOpacity(0.3), width: 0.8),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                widget.apiService.activeDatasetId ?? 'demo01',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  color: Color(0xFFC084FC),
                                ),
                              ),
                              if (widget.onSwitchDataset != null) ...[
                                const SizedBox(width: 4),
                                const Icon(Icons.swap_horiz_rounded, size: 14, color: Color(0xFFC084FC)),
                              ],
                            ],
                          ),
                        ),
                      ),

                    ],
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    "Real-time spatio-temporal tracking across monitored home anchors.",
                    style: TextStyle(fontSize: 14, color: AppTheme.textMuted, height: 1.35),
                  ),
                  const SizedBox(height: 14),
                  Builder(
                    builder: (context) {
                      final anchors = _events
                          .map((e) => e.destinationAnchor)
                          .where((a) => a != null && a.isNotEmpty)
                          .toSet()
                          .toList();
                      final anchorDisplay = anchors.isNotEmpty
                          ? anchors.join(", ")
                          : "Grounded Room Anchors";
                      final anchorCount = anchors.isNotEmpty ? anchors.length : 1;

                      final objects = _events
                          .map((e) => e.object)
                          .where((o) => o.isNotEmpty)
                          .toSet()
                          .toList();
                      final objectDisplay = objects.isNotEmpty
                          ? objects.join(", ")
                          : "Tracked Object";
                      final objectCount = objects.isNotEmpty ? objects.length : 1;

                      return Row(
                        children: [
                          _buildMetricTile(
                            "$anchorCount Active Anchor${anchorCount > 1 ? 's' : ''}",
                            anchorDisplay,
                            AppTheme.systemIndigo,
                          ),
                          const SizedBox(width: 10),
                          _buildMetricTile(
                            "$objectCount Instance${objectCount > 1 ? 's' : ''}",
                            objectDisplay,
                            AppTheme.primaryTeal,
                          ),
                        ],
                      );
                    },
                  ),
                ],
              ),
            ),

            const SizedBox(height: 14),

            // Dynamic Displaced Item Warning / Status Card
            Builder(
              builder: (context) {
                final lastEvent = _events.isNotEmpty ? _events.last : null;
                final isOnFloor = lastEvent != null && lastEvent.destinationRelation == 'on_floor';
                final isCarried = lastEvent != null && lastEvent.destinationRelation == 'carried_by_user';

                Color cardColor = AppTheme.systemGreen;
                IconData cardIcon = Icons.check_circle_outline_rounded;
                String cardText = "All tracked items are safely stored in their designated room anchors.";

                if (isOnFloor) {
                  cardColor = AppTheme.alertAmber;
                  cardIcon = Icons.warning_amber_rounded;
                  cardText = "Displaced Item Alert: ${lastEvent.object} left on the entrance floor (Fall Hazard)!";
                } else if (isCarried) {
                  cardColor = AppTheme.systemIndigo;
                  cardIcon = Icons.pan_tool_rounded;
                  cardText = "In-Transit Activity: ${lastEvent.object} is currently held and being moved.";
                }

                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    color: cardColor.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: cardColor.withOpacity(0.3), width: 0.8),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 34,
                        height: 34,
                        decoration: BoxDecoration(
                          color: cardColor.withOpacity(0.14),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(cardIcon, color: cardColor, size: 20),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          cardText,
                          style: TextStyle(
                            color: cardColor,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            letterSpacing: -0.1,
                            height: 1.3,
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
            const SizedBox(height: 14),

            // Patient Recent Search History Option
            _buildPatientSearchHistorySection(),
            const SizedBox(height: 18),

            // Timeline Header with Refresh Action
            Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: AppTheme.primaryTeal.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.timeline_rounded, color: AppTheme.primaryTeal, size: 18),
                ),
                const SizedBox(width: 10),
                const Text(
                  "Activity History Log",
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -0.3,
                    color: AppTheme.textHighContrast,
                  ),
                ),
                const Spacer(),
                SizedBox(
                  width: 36,
                  height: 36,
                  child: IconButton(
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                    icon: Container(
                      width: 32,
                      height: 32,
                      decoration: BoxDecoration(
                        color: AppTheme.primaryTeal.withOpacity(0.08),
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.refresh_rounded, color: AppTheme.primaryTeal, size: 16),
                    ),
                    tooltip: "Refresh Timeline",
                    onPressed: _loadTimeline,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),

            if (_isLoading)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: CircularProgressIndicator(color: AppTheme.primaryTeal),
                ),
              )
            else if (_events.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Text("No events recorded today.", style: TextStyle(color: AppTheme.textMuted, fontSize: 14)),
                ),
              )
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _events.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  final ev = _events[index];
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    decoration: AppTheme.iosCardDecoration(radius: 14),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            color: AppTheme.systemIndigo.withOpacity(0.12),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.arrow_forward_rounded, color: AppTheme.systemIndigo, size: 16),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                ev.summary,
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                  letterSpacing: -0.2,
                                  color: AppTheme.textHighContrast,
                                ),
                              ),
                              const SizedBox(height: 3),
                              Text(
                                "Window: ${ev.startTime.toStringAsFixed(1)}s - ${ev.endTime.toStringAsFixed(1)}s",
                                style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
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
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.25), width: 0.8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: -0.1)),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(color: AppTheme.textHighContrast, fontSize: 13, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }

  Widget _buildPatientSearchHistorySection() {
    final searches = widget.apiService.getRecentSearches(limit: 3);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.iosCardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppTheme.systemBlue.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.history_rounded, color: AppTheme.systemBlue, size: 18),
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "Patient Recent Search History",
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        letterSpacing: -0.3,
                        color: AppTheme.textHighContrast,
                      ),
                    ),
                    Text(
                      "Recent 3 queries recalled by patient",
                      style: TextStyle(fontSize: 12, color: AppTheme.textMuted),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppTheme.primaryTeal.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  "${searches.length} Recent",
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.primaryTeal,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Divider(color: AppTheme.cardBorder, height: 1),
          const SizedBox(height: 8),
          if (searches.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Center(
                child: Text(
                  "No patient searches recorded yet.",
                  style: TextStyle(fontSize: 13, color: AppTheme.textMuted),
                ),
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: searches.length,
              separatorBuilder: (_, __) => const Padding(
                padding: EdgeInsets.symmetric(vertical: 4),
                child: Divider(color: AppTheme.cardBorder, height: 1),
              ),
              itemBuilder: (context, index) {
                final item = searches[index];
                final queryDisplay = item.query.isNotEmpty
                    ? item.query[0].toUpperCase() + item.query.substring(1)
                    : item.query;
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    children: [
                      Container(
                        width: 36,
                        height: 36,
                        decoration: BoxDecoration(
                          color: AppTheme.primaryTeal.withOpacity(0.08),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          _getIconForQuery(item.query),
                          size: 18,
                          color: AppTheme.primaryTeal,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text(
                                  queryDisplay,
                                  style: const TextStyle(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.textHighContrast,
                                    letterSpacing: -0.2,
                                  ),
                                ),
                                const SizedBox(width: 6),
                                if (item.isPersistentMemory)
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: AppTheme.royalAmethyst.withOpacity(0.12),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: const Text(
                                      "✦ Memory",
                                      style: TextStyle(
                                        color: Color(0xFF92400E),
                                        fontSize: 10,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 2),
                            Text(
                              item.locationSummary,
                              style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        item.timeAgo,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: AppTheme.textMuted,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  IconData _getIconForQuery(String q) {
    switch (q.toLowerCase()) {
      case 'shoes':
        return Icons.snowshoeing_rounded;
      case 'keys':
        return Icons.key_rounded;
      case 'glasses':
        return Icons.visibility_rounded;
      case 'medicine':
        return Icons.medication_rounded;
      default:
        return Icons.search_rounded;
    }
  }
}
