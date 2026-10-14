import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../models/query_result.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';

class PatientView extends StatefulWidget {
  final ApiService apiService;
  final VoidCallback? onSwitchDataset;

  const PatientView({
    super.key,
    required this.apiService,
    this.onSwitchDataset,
  });

  @override
  State<PatientView> createState() => _PatientViewState();
}

class _PatientViewState extends State<PatientView> {
  QueryResult? _activeResult;
  bool _isLoading = false;
  String? _selectedCategory;
  final TextEditingController _searchController = TextEditingController();

  List<Map<String, dynamic>> _quickItems = [];

  String _getDatasetHumanTitle(String id) {
    final lower = id.toLowerCase();
    if (lower.contains('demo_pots') || lower.contains('pots')) {
      return 'Arrange Pots & Pans in Kitchen';
    } else if (lower.contains('demo03') || lower.contains('fridge')) {
      return 'Put Leftover Food Into Fridge Compartment';
    } else if (lower.contains('demo01') || lower.contains('shoes')) {
      return 'Put Shoes Into Storage Cabinet';
    } else if (lower.contains('demo06') || lower.contains('desk')) {
      return 'Bottle Relocation Between Desks';
    } else if (lower.contains('demo04') || lower.contains('trash')) {
      return 'Empty The Trash';
    }
    return 'Egocentric Scene: $id';
  }

  @override
  void initState() {
    super.initState();
    _configureQuickItems();
  }

  @override
  void didUpdateWidget(covariant PatientView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.apiService.activeDatasetId != widget.apiService.activeDatasetId) {
      _configureQuickItems();
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _configureQuickItems() {
    final ds = (widget.apiService.activeDatasetId ?? 'demo01').toLowerCase();
    if (ds.contains('demo04') || ds.contains('trash') || ds.contains('rubbish')) {
      _quickItems = [
        {'label': 'Garbage Bag', 'query': 'garbage bag', 'icon': Icons.shopping_bag_outlined, 'color': AppTheme.tealAccent},
        {'label': 'Rubbish', 'query': 'rubbish', 'icon': Icons.delete_outline_rounded, 'color': AppTheme.royalAmethyst},
        {'label': 'Plastic Bottle', 'query': 'plastic bottle', 'icon': Icons.local_drink_outlined, 'color': const Color(0xFF0EA5E9)},
        {'label': 'Food Container', 'query': 'food container', 'icon': Icons.inventory_2_outlined, 'color': AppTheme.alertAmber},
      ];
    } else if (ds.contains('demo03') || ds.contains('demo_pots') || ds.contains('pot') || ds.contains('kitchen') || ds.contains('food') || ds.contains('fridge')) {
      _quickItems = [
        {'label': 'Cooking Pot', 'query': 'cooking pot', 'icon': Icons.soup_kitchen_rounded, 'color': AppTheme.tealAccent},
        {'label': 'Bowl', 'query': 'bowl', 'icon': Icons.rice_bowl_rounded, 'color': AppTheme.royalAmethyst},
        {'label': 'Frying Pan', 'query': 'frying pan', 'icon': Icons.restaurant_rounded, 'color': const Color(0xFF0EA5E9)},
        {'label': 'Food / Leftovers', 'query': 'food', 'icon': Icons.lunch_dining_rounded, 'color': AppTheme.alertAmber},
      ];
    } else if (ds.contains('demo06') || ds.contains('self') || ds.contains('desk') || ds.contains('office')) {
      _quickItems = [
        {'label': 'Water Bottle', 'query': 'water bottle', 'icon': Icons.local_drink_rounded, 'color': AppTheme.tealAccent},
        {'label': 'Desk #1', 'query': 'bottle on desk 1', 'icon': Icons.table_restaurant_rounded, 'color': AppTheme.royalAmethyst},
        {'label': 'Desk #2', 'query': 'bottle on desk 2', 'icon': Icons.desk_rounded, 'color': AppTheme.alertAmber},
        {'label': 'Keys', 'query': 'keys', 'icon': Icons.key_rounded, 'color': const Color(0xFFEC4899)},
      ];
    } else if (ds.contains('demo05') || ds.contains('cloth') || ds.contains('laundry')) {
      _quickItems = [
        {'label': 'Clothes', 'query': 'clothes', 'icon': Icons.checkroom_rounded, 'color': AppTheme.tealAccent},
        {'label': 'Towel', 'query': 'towel', 'icon': Icons.dry_cleaning_rounded, 'color': AppTheme.royalAmethyst},
        {'label': 'Laundry Hamper', 'query': 'laundry', 'icon': Icons.inventory_2_rounded, 'color': AppTheme.alertAmber},
        {'label': 'Basket', 'query': 'basket', 'icon': Icons.shopping_basket_rounded, 'color': const Color(0xFFEC4899)},
      ];
    } else {
      _quickItems = [
        {'label': 'Active Shoes', 'query': 'shoes', 'icon': Icons.snowshoeing_rounded, 'color': AppTheme.royalAmethyst},
        {'label': 'Cabinet Shelf', 'query': 'storage cabinet', 'icon': Icons.inventory_2_rounded, 'color': AppTheme.tealAccent},
        {'label': 'Keys', 'query': 'keys', 'icon': Icons.key_rounded, 'color': AppTheme.alertAmber},
        {'label': 'Water Bottle', 'query': 'water bottle', 'icon': Icons.local_drink_rounded, 'color': const Color(0xFF0EA5E9)},
      ];
    }
  }

  Future<void> _executeQuery(String item) async {
    final trimmed = item.trim();
    if (trimmed.isEmpty) return;

    setState(() {
      _isLoading = true;
      _selectedCategory = trimmed;
    });

    final res = await widget.apiService.queryItem(trimmed);
    widget.apiService.recordSearch(res);

    if (mounted) {
      setState(() {
        _isLoading = false;
        _activeResult = res;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final activeId = widget.apiService.activeDatasetId ?? 'demo01';
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // High-Visibility Active Video Scene Switcher Card
          if (widget.onSwitchDataset != null)
            GestureDetector(
              onTap: widget.onSwitchDataset,
              behavior: HitTestBehavior.opaque,
              child: Container(
                margin: const EdgeInsets.only(bottom: 14),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
                decoration: BoxDecoration(
                  color: AppTheme.royalAmethyst.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.royalAmethyst.withOpacity(0.35), width: 1.2),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: AppTheme.royalAmethyst.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(Icons.video_library_rounded, size: 20, color: AppTheme.royalAmethyst),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Text(
                                "ACTIVE VIDEO SCENE",
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w800,
                                  color: AppTheme.royalAmethyst,
                                  letterSpacing: 0.6,
                                ),
                              ),
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                                decoration: BoxDecoration(
                                  color: AppTheme.royalAmethyst.withOpacity(0.2),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  activeId.toUpperCase(),
                                  style: const TextStyle(
                                    fontSize: 9,
                                    fontWeight: FontWeight.bold,
                                    color: AppTheme.textHighContrast,
                                    fontFamily: 'monospace',
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            _getDatasetHumanTitle(activeId),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textHighContrast,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppTheme.darkCanvas,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AppTheme.cardBorder, width: 0.8),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            "Switch",
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.royalAmethyst,
                            ),
                          ),
                          SizedBox(width: 2),
                          Icon(Icons.keyboard_arrow_down_rounded, size: 16, color: AppTheme.royalAmethyst),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          // Dementia-friendly large instruction banner (Apple Inset Card)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: AppTheme.iosCardDecoration(
              radius: AppTheme.cardCornerRadius,
            ),
            child: Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: AppTheme.primaryTeal.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.touch_app_rounded, color: AppTheme.primaryTeal, size: 22),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        "Ask where any object is right now",
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          letterSpacing: -0.3,
                          color: AppTheme.textHighContrast,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        "Tracking Scene: $activeId",
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          color: AppTheme.tealAccent,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Universal Object Search Input Bar
          Container(
            decoration: BoxDecoration(
              color: AppTheme.darkSurface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.cardBorder, width: 0.8),
            ),
            child: Row(
              children: [
                const Padding(
                  padding: EdgeInsets.only(left: 14, right: 10),
                  child: Icon(Icons.search_rounded, color: AppTheme.textMuted, size: 22),
                ),
                Expanded(
                  child: TextField(
                    controller: _searchController,
                    style: const TextStyle(color: AppTheme.textHighContrast, fontSize: 16),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (val) {
                      HapticFeedback.lightImpact();
                      _executeQuery(val);
                    },
                    decoration: InputDecoration(
                      hintText: "Type any item (e.g. pot, bowl, shoes)...",
                      hintStyle: const TextStyle(color: AppTheme.tertiaryLabel, fontSize: 14),
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(vertical: 14),
                      suffixIcon: _searchController.text.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear_rounded, color: AppTheme.textMuted, size: 18),
                              onPressed: () {
                                _searchController.clear();
                                setState(() {});
                              },
                            )
                          : null,
                    ),
                    onChanged: (val) => setState(() {}),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: IconButton(
                    style: IconButton.styleFrom(
                      backgroundColor: AppTheme.primaryTeal.withOpacity(0.16),
                      foregroundColor: AppTheme.primaryTeal,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: const Icon(Icons.arrow_forward_rounded, size: 20),
                    onPressed: () {
                      HapticFeedback.selectionClick();
                      _executeQuery(_searchController.text.isNotEmpty ? _searchController.text : (_quickItems.first['query'] as String));
                    },
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // 2x2 Big Touch Targets (Apple Grouped Grid for Active Video)
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 1.35,
            ),
            itemCount: _quickItems.length,
            itemBuilder: (context, index) {
              final it = _quickItems[index];
              final isSelected = _selectedCategory == it['query'];
              final itemColor = it['color'] as Color;
              return InkWell(
                onTap: () {
                  HapticFeedback.selectionClick();
                  _searchController.text = it['label'] as String;
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
                        width: 46,
                        height: 46,
                        decoration: BoxDecoration(
                          color: itemColor.withOpacity(0.12),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(it['icon'] as IconData, size: 26, color: itemColor),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        it['label'] as String,
                        style: TextStyle(
                          fontSize: 16,
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
          const SizedBox(height: 14),

          // Voice Query Bar (Apple Prominent Action Button)
          InkWell(
            onTap: () {
              HapticFeedback.lightImpact();
              final targetQuery = _searchController.text.isNotEmpty
                  ? _searchController.text
                  : (_selectedCategory ?? (_quickItems.isNotEmpty ? _quickItems.first['query'] as String : 'object'));
              _executeQuery(targetQuery);
            },
            borderRadius: BorderRadius.circular(18),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppTheme.primaryTeal, Color(0xFFB45309)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(18),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryTeal.withOpacity(0.25),
                    blurRadius: 14,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.mic_rounded, color: Colors.white, size: 24),
                  SizedBox(width: 10),
                  Text(
                    "Tap to Ask by Voice",
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.3,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),

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
    final activeId = widget.apiService.activeDatasetId ?? 'demo01';
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
                  color: (result.found ? AppTheme.primaryTeal : AppTheme.alertAmber).withOpacity(0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      result.found ? Icons.check_circle_rounded : Icons.info_outline_rounded,
                      color: result.found ? AppTheme.primaryTeal : AppTheme.alertAmber,
                      size: 16,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      result.found ? "LOCATED" : "NOT FOUND",
                      style: TextStyle(
                        color: result.found ? AppTheme.primaryTeal : AppTheme.alertAmber,
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                        letterSpacing: 0.2,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.cardBorder.withOpacity(0.4),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  activeId,
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textMuted),
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
                      color: Color(0xFFC084FC),
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
              fontSize: 20,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.4,
              color: AppTheme.textHighContrast,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 14),

          // Context & Recency Inset Info
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
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
                    result.anchorLabel != null
                        ? "${result.anchorLabel}${result.relativeDistanceM != null ? ' (~${result.relativeDistanceM}m)' : ''}"
                        : "Room Anchor",
                    style: const TextStyle(
                      color: AppTheme.tealAccent,
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
