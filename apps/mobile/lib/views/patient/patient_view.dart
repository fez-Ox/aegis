import 'package:flutter/material.dart';
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
    {'label': 'Medicine', 'query': 'medicine', 'icon': Icons.medication_rounded, 'color': const Color(0xFFEC4899)},
  ];

  Future<void> _executeQuery(String item) async {
    setState(() {
      _isLoading = true;
      _selectedCategory = item;
    });

    final res = await widget.apiService.queryItem(item);

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
          // Dementia-friendly large instruction banner
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppTheme.darkSurface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFF334155), width: 1.5),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryTeal.withOpacity(0.2),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.touch_app_rounded, color: AppTheme.tealAccent, size: 28),
                ),
                const SizedBox(width: 14),
                const Expanded(
                  child: Text(
                    "Tap an item to find where it is right now",
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: AppTheme.textHighContrast),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // 2x2 Big Touch Targets
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 16,
              mainAxisSpacing: 16,
              childAspectRatio: 1.25,
            ),
            itemCount: _quickItems.length,
            itemBuilder: (context, index) {
              final it = _quickItems[index];
              final isSelected = _selectedCategory == it['query'];
              return InkWell(
                onTap: () => _executeQuery(it['query'] as String),
                borderRadius: BorderRadius.circular(24),
                child: Container(
                  decoration: BoxDecoration(
                    color: isSelected ? AppTheme.primaryTeal.withOpacity(0.3) : AppTheme.darkSurface,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(
                      color: isSelected ? AppTheme.tealAccent : const Color(0xFF334155),
                      width: isSelected ? 3.0 : 1.5,
                    ),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(it['icon'] as IconData, size: 44, color: it['color'] as Color),
                      const SizedBox(height: 10),
                      Text(
                        it['label'] as String,
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.textHighContrast),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 20),

          // Voice Query Bar
          InkWell(
            onTap: () => _executeQuery('shoes'),
            borderRadius: BorderRadius.circular(24),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 20),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppTheme.primaryTeal, Color(0xFF0F766E)],
                ),
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(color: AppTheme.primaryTeal.withOpacity(0.3), blurRadius: 12, offset: const Offset(0, 4)),
                ],
              ),
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.mic_rounded, color: Colors.white, size: 30),
                  SizedBox(width: 12),
                  Text(
                    "Tap to Ask by Voice",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

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
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: AppTheme.darkSurface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppTheme.tealAccent, width: 2.0),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.4), blurRadius: 16, offset: const Offset(0, 6)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.primaryTeal.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.check_circle_rounded, color: AppTheme.tealAccent, size: 18),
                    const SizedBox(width: 6),
                    Text(
                      result.found ? "LOCATED" : "NOT FOUND",
                      style: const TextStyle(color: AppTheme.tealAccent, fontWeight: FontWeight.bold, fontSize: 13),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              if (result.isPersistentMemory)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppTheme.royalAmethyst.withOpacity(0.25),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Text(
                    "✦ PERSISTENT MEMORY",
                    style: TextStyle(color: Color(0xFFA5B4FC), fontWeight: FontWeight.w700, fontSize: 11),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),

          // Main location text
          Text(
            result.locationSummary,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: AppTheme.textHighContrast, height: 1.3),
          ),
          const SizedBox(height: 12),

          // Context & Recency
          Row(
            children: [
              const Icon(Icons.access_time_rounded, color: AppTheme.textMuted, size: 18),
              const SizedBox(width: 6),
              Text(result.lastSeenTimeAgo, style: const TextStyle(color: AppTheme.textMuted, fontSize: 15)),
              const SizedBox(width: 16),
              const Icon(Icons.room_rounded, color: AppTheme.royalAmethyst, size: 18),
              const SizedBox(width: 6),
              Text(result.anchorLabel ?? "Room Anchor", style: const TextStyle(color: Color(0xFFA5B4FC), fontSize: 15, fontWeight: FontWeight.w600)),
            ],
          ),
        ],
      ),
    );
  }
}
