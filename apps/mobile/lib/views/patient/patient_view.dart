import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../models/query_result.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';

class PatientView extends StatefulWidget {
  final ApiService apiService;

  const PatientView({super.key, required this.apiService});

  @override
  State<PatientView> createState() => _PatientViewState();
}

class _PatientViewState extends State<PatientView> {
  QueryResult? _activeResult;
  bool _isLoading = false;
  String? _selectedCategory;

  final List<Map<String, dynamic>> _quickItems = [
    {'label': 'Shoes', 'query': 'shoes', 'icon': Icons.snowshoeing_rounded, 'color': AppTheme.tealAccent},
    {'label': 'Keys', 'query': 'keys', 'icon': Icons.key_rounded, 'color': AppTheme.royalAmethyst},
    {'label': 'Glasses', 'query': 'glasses', 'icon': Icons.visibility_rounded, 'color': AppTheme.alertAmber},
    {'label': 'Medicine', 'query': 'medicine', 'icon': Icons.medication_rounded, 'color': const Color(0xFFD97706)},
  ];

  Future<void> _executeQuery(String item) async {
    setState(() {
      _isLoading = true;
      _selectedCategory = item;
    });

    final res = await widget.apiService.queryItem(item);
    widget.apiService.recordSearch(res);

    setState(() {
      _isLoading = false;
      _activeResult = res;
    });
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Dementia-friendly large instruction banner (Apple Inset Card)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
            decoration: AppTheme.iosCardDecoration(
              radius: AppTheme.cardCornerRadius,
            ),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: AppTheme.primaryTeal.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.touch_app_rounded, color: AppTheme.primaryTeal, size: 24),
                ),
                const SizedBox(width: 14),
                const Expanded(
                  child: Text(
                    "Tap an item to find where it is right now",
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w600,
                      letterSpacing: -0.3,
                      color: AppTheme.textHighContrast,
                      height: 1.3,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // 2x2 Big Touch Targets (Apple Grouped Grid)
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 14,
              mainAxisSpacing: 14,
              childAspectRatio: 1.25,
            ),
            itemCount: _quickItems.length,
            itemBuilder: (context, index) {
              final it = _quickItems[index];
              final isSelected = _selectedCategory == it['query'];
              final itemColor = it['color'] as Color;
              return InkWell(
                onTap: () {
                  HapticFeedback.selectionClick();
                  _executeQuery(it['query'] as String);
                },
                borderRadius: BorderRadius.circular(18),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  curve: Curves.easeOut,
                  decoration: BoxDecoration(
                    color: isSelected ? itemColor.withOpacity(0.08) : AppTheme.darkSurface,
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(
                      color: isSelected ? itemColor : AppTheme.cardBorder,
                      width: isSelected ? 2.5 : 0.8,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: isSelected ? itemColor.withOpacity(0.12) : const Color(0x06000000),
                        blurRadius: isSelected ? 12 : 6,
                        offset: const Offset(0, 3),
                      ),
                    ],
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        width: 54,
                        height: 54,
                        decoration: BoxDecoration(
                          color: itemColor.withOpacity(0.12),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(it['icon'] as IconData, size: 30, color: itemColor),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        it['label'] as String,
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          letterSpacing: -0.3,
                          color: isSelected ? itemColor : AppTheme.textHighContrast,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 16),

          // Voice Query Bar (Apple Prominent Action Button)
          InkWell(
            onTap: () {
              HapticFeedback.lightImpact();
              _executeQuery('shoes');
            },
            borderRadius: BorderRadius.circular(18),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppTheme.primaryTeal, Color(0xFFB45309)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(18),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryTeal.withOpacity(0.28),
                    blurRadius: 14,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.mic_rounded, color: Colors.white, size: 26),
                  SizedBox(width: 10),
                  Text(
                    "Tap to Ask by Voice",
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.3,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),

          // Active Result Display
          if (_isLoading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: CircularProgressIndicator(color: AppTheme.tealAccent),
              ),
            )
          else if (_activeResult != null)
            _buildResultCard(_activeResult!),
        ],
      ),
    );
  }

  Widget _buildResultCard(QueryResult result) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.darkSurface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.primaryTeal.withOpacity(0.35), width: 1.2),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0C000000),
            blurRadius: 16,
            offset: Offset(0, 5),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: AppTheme.primaryTeal.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.check_circle_rounded, color: AppTheme.primaryTeal, size: 16),
                    const SizedBox(width: 6),
                    Text(
                      result.found ? "LOCATED" : "NOT FOUND",
                      style: const TextStyle(
                        color: AppTheme.primaryTeal,
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                        letterSpacing: 0.2,
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              if (result.isPersistentMemory)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: AppTheme.royalAmethyst.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Text(
                    "✦ PERSISTENT MEMORY",
                    style: TextStyle(
                      color: Color(0xFF92400E),
                      fontWeight: FontWeight.w700,
                      fontSize: 11,
                      letterSpacing: 0.1,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 14),

          // Main location text
          Text(
            result.locationSummary,
            style: const TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.4,
              color: AppTheme.textHighContrast,
              height: 1.3,
            ),
          ),
          const SizedBox(height: 14),

          // Context & Recency Inset Info
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: AppTheme.darkCanvas,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                const Icon(Icons.access_time_rounded, color: AppTheme.textMuted, size: 16),
                const SizedBox(width: 6),
                Text(
                  result.lastSeenTimeAgo,
                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 13, fontWeight: FontWeight.w500),
                ),
                const SizedBox(width: 14),
                const Icon(Icons.room_rounded, color: AppTheme.primaryTeal, size: 16),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    result.anchorLabel ?? "Room Anchor",
                    style: const TextStyle(
                      color: Color(0xFF92400E),
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      letterSpacing: -0.1,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
