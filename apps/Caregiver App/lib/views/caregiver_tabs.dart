import 'package:flutter/material.dart';

import 'enroll_dialog.dart';

import '../models/memory_answer.dart';
import '../models/object_tile.dart';
import '../models/search_entry.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import '../widgets/object_icon.dart';

/// Search history with local filtering by time and ambiguity outcome.
class SearchHistoryTab extends StatefulWidget {
  final List<SearchEntry> entries;

  const SearchHistoryTab({
    super.key,
    required this.entries,
  });

  @override
  State<SearchHistoryTab> createState() => _SearchHistoryTabState();
}

class _SearchHistoryTabState extends State<SearchHistoryTab> {
  String _period = 'all';
  bool _ambiguousOnly = false;
  String? _expanded;

  bool _inPeriod(SearchEntry entry) {
    final at = DateTime.tryParse(entry.at);
    if (at == null) return true;
    final now = DateTime.now();
    return switch (_period) {
      'today' => now.difference(at) < const Duration(days: 1),
      'week' => now.difference(at) < const Duration(days: 7),
      'month' => now.difference(at) < const Duration(days: 30),
      _ => true,
    };
  }

  @override
  Widget build(BuildContext context) {
    final entries = widget.entries
        .where((e) => _inPeriod(e) && (!_ambiguousOnly || e.ambiguous))
        .toList();
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
      children: [
        const Text(
          'Search History',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: PatientTheme.ivory,
          ),
        ),
        const SizedBox(height: 14),
        Row(
          children: [
            for (final p in ['today', 'week', 'month', 'all'])
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: _FilterButton(
                    label: switch (p) {
                      'today' => 'Today',
                      'week' => 'Week',
                      'month' => 'Month',
                      _ => 'All',
                    },
                    selected: _period == p,
                    onTap: () => setState(() => _period = p),
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 10),
        Align(
          alignment: Alignment.centerLeft,
          child: _FilterButton(
            label: _ambiguousOnly ? 'Ambiguous only ✓' : 'Show ambiguous only',
            selected: _ambiguousOnly,
            onTap: () => setState(() => _ambiguousOnly = !_ambiguousOnly),
          ),
        ),
        const SizedBox(height: 16),
        if (entries.isEmpty)
          Container(
            padding: const EdgeInsets.all(24),
            decoration: PatientTheme.insetCard(),
            child: const Text(
              'No searches in this period',
              key: Key('caregiver-history-empty'),
              textAlign: TextAlign.center,
              style: TextStyle(color: PatientTheme.ivory300),
            ),
          )
        else
          ...entries.map(
            (e) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: PatientTheme.insetCard(),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      e.query,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: PatientTheme.ivory,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      e.answer,
                      style: const TextStyle(
                        fontSize: 13,
                        color: PatientTheme.ivory300,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      children: [
                        _chip(e.mode),
                        if (e.ambiguous) _chip('ambiguous'),
                        if (e.tier != null) _chip(e.tier!),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Text(
                          e.at.length >= 16 ? e.at.substring(0, 16) : e.at,
                          style: const TextStyle(
                            fontSize: 11,
                            color: PatientTheme.ivory400,
                          ),
                        ),
                        const Spacer(),
                        if (e.candidates.isNotEmpty)
                          TextButton(
                            key: Key('history-expand-${e.query}'),
                            onPressed: () => setState(
                              () => _expanded =
                                  _expanded == e.query ? null : e.query,
                            ),
                            child: Text(
                              _expanded == e.query
                                  ? 'Hide candidates'
                                  : 'Candidates (${e.candidates.length})',
                              style: const TextStyle(fontSize: 11),
                            ),
                          ),
                      ],
                    ),
                    if (_expanded == e.query && e.candidates.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'CANDIDATES',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1,
                                color: PatientTheme.ochre,
                              ),
                            ),
                            ...List.generate(
                              e.candidates.length,
                              (index) => Text(
                                '${index + 1}. ${e.candidates[index]}',
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: PatientTheme.ivory300,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
  Widget _chip(String label) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: PatientTheme.surfaceCard,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: PatientTheme.borderStrong),
        ),
        child: Text(
          label,
          style: const TextStyle(
            fontSize: 10,
            color: PatientTheme.ivory300,
          ),
        ),
      );
}

class _FilterButton extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _FilterButton({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 40,
      child: OutlinedButton(
        onPressed: onTap,
        style: OutlinedButton.styleFrom(
          foregroundColor:
              selected ? PatientTheme.canvas : PatientTheme.ivory300,
          backgroundColor: selected ? PatientTheme.ochre : null,
          side: const BorderSide(color: PatientTheme.borderStrong),
          padding: const EdgeInsets.symmetric(horizontal: 8),
        ),
        child: Text(
          label,
          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}

/// Object tracking: server-backed object list and sighting history from
/// /api/v1/timeline (filtered on-device by object label).
class TrackingTab extends StatefulWidget {
  final ApiService apiService;
  final List<ObjectTile> tiles;
  /// Increment to open the Interactions view from the header button.
  final int interactionRequest;

  const TrackingTab({
    super.key,
    required this.apiService,
    required this.tiles,
    this.interactionRequest = 0,
  });

  @override
  State<TrackingTab> createState() => _TrackingTabState();
}

class _TrackingTabState extends State<TrackingTab> {
  static const _filters = ['today', 'week', 'month', 'all'];

  List<Map<String, dynamic>> _events = [];
  ObjectTile? _selected;
  MemoryAnswer? _current;
  String? _error;
  bool _loading = false;
  String _view = 'list'; // list | detail | interactions
  String _historyFilter = 'all';
  String _interactionFilter = 'today';
  String _interactionMode = 'frequent';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant TrackingTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.interactionRequest != oldWidget.interactionRequest) {
      setState(() => _view = 'interactions');
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final events = await widget.apiService.timeline();
      if (!mounted) return;
      setState(() => _events = events);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadDetail(ObjectTile tile) async {
    setState(() => _current = null);
    try {
      final answer =
          await widget.apiService.queryItem(tile.label.toLowerCase());
      if (!mounted) return;
      setState(() => _current = answer);
    } on ApiException {
      // Current location is optional; sightings are still shown.
    }
  }

  DateTime? _timeOf(Map<String, dynamic> event) {
    final raw = event['start_wallclock'] ?? event['end_wallclock'];
    return raw is String ? DateTime.tryParse(raw) : null;
  }

  bool _inPeriod(Map<String, dynamic> event, String period) {
    if (period == 'all') return true;
    final at = _timeOf(event);
    if (at == null) return true;
    final days = switch (period) {
      'today' => 1,
      'week' => 7,
      _ => 30,
    };
    return DateTime.now().difference(at) < Duration(days: days);
  }

  List<Map<String, dynamic>> _eventsFor(ObjectTile tile) => _events.where((e) {
        final obj = (e['object'] as String?) ?? '';
        return obj.toLowerCase().contains(tile.label.toLowerCase()) &&
            _inPeriod(e, _historyFilter);
      }).toList();

  @override
  Widget build(BuildContext context) {
    return switch (_view) {
      'detail' when _selected != null => _detailView(_selected!),
      'interactions' => _interactionsView(),
      _ => _listView(),
    };
  }

  Widget _header(String title, {VoidCallback? onBack}) => Row(
        children: [
          if (onBack != null)
            IconButton(
              key: const Key('caregiver-tracking-back'),
              onPressed: onBack,
              icon: const Icon(Icons.arrow_back),
            ),
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: PatientTheme.ivory,
              ),
            ),
          ),
        ],
      );

  Widget _listView() => ListView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
        children: [
          Row(
            children: [
              const Text(
                'Tracked Objects',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: PatientTheme.ivory,
                ),
              ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: PatientTheme.ochre.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: PatientTheme.ochre),
                ),
                child: Text(
                  '${widget.tiles.length} Items',
                  style: const TextStyle(
                    fontSize: 11,
                    color: PatientTheme.ochre,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          if (_loading)
            const Center(
              child: SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text(
                _error!,
                style: const TextStyle(color: Colors.redAccent, fontSize: 12),
              ),
            ),
          const SizedBox(height: 14),
          if (widget.tiles.isEmpty)
            Container(
              padding: const EdgeInsets.all(24),
              decoration: PatientTheme.insetCard(),
              child: const Text(
                'No objects in memory yet',
                key: Key('caregiver-tracking-empty'),
                textAlign: TextAlign.center,
                style: TextStyle(color: PatientTheme.ivory300),
              ),
            )
          else
            ...widget.tiles.map(
              (tile) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  key: Key(
                    'caregiver-track-${tile.label.toLowerCase().replaceAll(' ', '-')}',
                  ),
                  leading: Icon(iconFor(tile.kind), color: PatientTheme.ochre),
                  title: Text(
                    tile.label,
                    style: const TextStyle(color: PatientTheme.ivory),
                  ),
                  onTap: () {
                    setState(() {
                      _selected = tile;
                      _view = 'detail';
                    });
                    _loadDetail(tile);
                  },
                ),
              ),
            ),
        ],
      );

  Widget _detailView(ObjectTile tile) {
    final matches = _eventsFor(tile);
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
      children: [
        Row(
          children: [
            IconButton(
              key: const Key('caregiver-tracking-back'),
              onPressed: () => setState(() => _view = 'list'),
              icon: const Icon(Icons.arrow_back),
            ),
            Icon(iconFor(tile.kind), color: PatientTheme.ochre),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                tile.label,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: PatientTheme.ivory,
                ),
              ),
            ),
            IconButton(
              key: const Key('caregiver-history-settings'),
              tooltip: 'History timeframe',
              onPressed: _showHistorySettings,
              icon: const Icon(Icons.settings_outlined),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: Text(
            _historyFilter == 'all' ? 'All time' : 'This $_historyFilter',
            style: const TextStyle(fontSize: 11, color: PatientTheme.ochre),
          ),
        ),
        const SizedBox(height: 12),
        if (_current != null && _current!.candidates.isNotEmpty)
          Container(
            padding: const EdgeInsets.all(14),
            decoration: PatientTheme.insetCard(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'LAST KNOWN LOCATION',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1,
                    color: PatientTheme.ochre,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  _current!.candidates.first.place,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    color: PatientTheme.ivory,
                  ),
                ),
                if (_current!.candidates.first.detail.isNotEmpty)
                  Text(
                    _current!.candidates.first.detail,
                    style: const TextStyle(
                      fontSize: 13,
                      color: PatientTheme.ivory300,
                    ),
                  ),
              ],
            ),
          ),
        const SizedBox(height: 12),
        Text(
          '${matches.length} sightings in memory',
          style: const TextStyle(color: PatientTheme.ivory300, fontSize: 13),
        ),
        const SizedBox(height: 10),
        if (matches.isEmpty)
          Container(
            padding: const EdgeInsets.all(20),
            decoration: PatientTheme.insetCard(),
            child: const Text(
              'No sighting history for this object',
              key: Key('caregiver-history-no-sightings'),
              textAlign: TextAlign.center,
              style: TextStyle(color: PatientTheme.ivory300),
            ),
          )
        else
          ...matches.map(
            (e) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: PatientTheme.insetCard(),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      (e['event_type'] as String?) ?? 'event',
                      style: const TextStyle(
                        color: PatientTheme.ochre,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      (e['summary'] as String?) ?? '',
                      style: const TextStyle(
                        color: PatientTheme.ivory300,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }

  Future<void> _showHistorySettings() async {
    await showModalBottomSheet<String>(
      context: context,
      backgroundColor: PatientTheme.surfaceCard,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'History Timeframe',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: PatientTheme.ivory,
                ),
              ),
            ),
            ...['today', 'week', 'month', 'all'].map(
              (value) => ListTile(
                key: Key('history-filter-$value'),
                title: Text(
                  switch (value) {
                    'today' => 'Today only',
                    'week' => 'This week',
                    'month' => 'This month',
                    _ => 'All time',
                  },
                  style: const TextStyle(color: PatientTheme.ivory),
                ),
                trailing: _historyFilter == value
                    ? const Icon(Icons.check, color: PatientTheme.ochre)
                    : null,
                onTap: () => Navigator.pop(context, value),
              ),
            ),
          ],
        ),
      ),
    ).then((value) {
      if (value != null && mounted) setState(() => _historyFilter = value);
    });
  }

  Widget _interactionsView() {
    final counts = <String, int>{};
    final latest = <String, DateTime>{};
    for (final event in _events.where((e) => _inPeriod(e, _interactionFilter))) {
      final object = (event['object'] as String?) ?? '';
      if (object.isEmpty) continue;
      final name = object.replaceFirst(RegExp(r'\s*#\d+.*$'), '').trim();
      counts[name] = (counts[name] ?? 0) + 1;
      final at = _timeOf(event);
      if (at != null &&
          (!latest.containsKey(name) || at.isAfter(latest[name]!))) {
        latest[name] = at;
      }
    }
    final ranked = counts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final recent = latest.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final maxCount = ranked.isEmpty ? 1 : ranked.first.value;

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
      children: [
        _header(
          'Interactions',
          onBack: () => setState(() => _view = 'list'),
        ),
        const SizedBox(height: 14),
        Row(
          children: [
            Expanded(
              child: _FilterButton(
                label: 'Most Recent',
                selected: _interactionMode == 'recent',
                onTap: () => setState(() => _interactionMode = 'recent'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _FilterButton(
                label: 'Most Frequent',
                selected: _interactionMode == 'frequent',
                onTap: () => setState(() => _interactionMode = 'frequent'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            for (final filter in _filters)
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(right: 5),
                  child: _FilterButton(
                    label: switch (filter) {
                      'today' => 'Today',
                      'week' => 'Week',
                      'month' => 'Month',
                      _ => 'All',
                    },
                    selected: _interactionFilter == filter,
                    onTap: () =>
                        setState(() => _interactionFilter = filter),
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 18),
        if (_interactionMode == 'frequent') ...[
          const Text(
            'Most frequently interacted with objects',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: PatientTheme.ochre,
            ),
          ),
          const SizedBox(height: 10),
          if (ranked.isEmpty)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Text(
                'No interactions in this period',
                textAlign: TextAlign.center,
                style: TextStyle(color: PatientTheme.ivory300),
              ),
            )
          else
            ...List.generate(ranked.length, (index) {
              final entry = ranked[index];
              final pct = (entry.value / maxCount * 100).round().clamp(8, 100);
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: PatientTheme.insetCard(),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            width: 22,
                            height: 22,
                            decoration: BoxDecoration(
                              color: index == 0
                                  ? PatientTheme.ochre
                                  : PatientTheme.border,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Center(
                              child: Text(
                                '${index + 1}',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                  color: index == 0
                                      ? PatientTheme.canvas
                                      : PatientTheme.ivory,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              entry.key,
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                color: PatientTheme.ivory,
                              ),
                            ),
                          ),
                          Text(
                            '${entry.value} interactions',
                            style: const TextStyle(
                              fontSize: 11,
                              color: PatientTheme.ochre,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: pct / 100,
                          minHeight: 6,
                          backgroundColor: PatientTheme.border,
                          color: PatientTheme.ochre,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }),
        ] else ...[
          const Text(
            'Most recent interacted with objects',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: PatientTheme.ochre,
            ),
          ),
          const SizedBox(height: 10),
          if (recent.isEmpty)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Text(
                'No interactions in this period',
                textAlign: TextAlign.center,
                style: TextStyle(color: PatientTheme.ivory300),
              ),
            )
          else
            ...recent.map(
              (entry) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: PatientTheme.insetCard(),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.inventory_2_outlined,
                        size: 18,
                        color: PatientTheme.ochre,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          entry.key,
                          style: const TextStyle(color: PatientTheme.ivory),
                        ),
                      ),
                      Text(
                        entry.value.toIso8601String().substring(0, 16),
                        style: const TextStyle(
                          fontSize: 11,
                          color: PatientTheme.ivory400,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ],
    );
  }
}

class InteriorTab extends StatefulWidget {
  final ApiService apiService;
  final List<ObjectTile> tiles;

  const InteriorTab({
    super.key,
    required this.apiService,
    required this.tiles,
  });

  @override
  State<InteriorTab> createState() => _InteriorTabState();
}

class _InteriorTabState extends State<InteriorTab> {
  List<Map<String, dynamic>> _rooms = [];
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final rooms = await widget.apiService.rooms();
      if (!mounted) return;
      setState(() => _rooms = rooms);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _rename(Map<String, dynamic> room) async {
    final id = room['room_id'];
    if (id is! int) return;
    final controller = TextEditingController(
      text: (room['label'] as String?) ?? '',
    );
    final saved = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: PatientTheme.surfaceCard,
        title: const Text(
          'Rename room',
          style: TextStyle(color: PatientTheme.ivory, fontSize: 18),
        ),
        content: TextField(
          key: const Key('caregiver-rename-field'),
          controller: controller,
          autofocus: true,
          style: const TextStyle(color: PatientTheme.ivory),
          decoration: const InputDecoration(hintText: 'New room name'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('caregiver-rename-save'),
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (saved == null || saved.isEmpty) return;
    try {
      await widget.apiService.renameRoom(id, saved);
      if (mounted) _load();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message)),
        );
      }
    }
  }

  Future<void> _enroll() async {
    await showDialog<bool>(
      context: context,
      builder: (context) => EnrollDialog(
        apiService: widget.apiService,
        objectLabels: widget.tiles.map((t) => t.label).toList(),
        roomLabels: _rooms
            .map((r) => (r['label'] as String?) ?? '')
            .where((s) => s.isNotEmpty)
            .toList(),
      ),
    );
  }

  static List<String> _labels(dynamic values) {
    return (values as List? ?? const [])
        .map((v) => v is Map ? (v['label'] as String?) ?? '' : '$v')
        .where((s) => s.isNotEmpty)
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
      children: [
        Row(
          children: [
            const Text(
              'Interior Structure',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: PatientTheme.ivory,
              ),
            ),
            const Spacer(),
            if (_loading)
              const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
          ],
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: OutlinedButton.icon(
            key: const Key('caregiver-enroll'),
            onPressed: _enroll,
            icon: const Icon(Icons.person_add_outlined, size: 16),
            label: const Text('Add personal item'),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '${_rooms.length} rooms in memory',
          style: const TextStyle(fontSize: 12, color: PatientTheme.ivory400),
        ),
        const SizedBox(height: 14),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              _error!,
              style: const TextStyle(color: Colors.redAccent, fontSize: 12),
            ),
          ),
        if (_rooms.isEmpty && !_loading)
          Container(
            padding: const EdgeInsets.all(24),
            decoration: PatientTheme.insetCard(),
            child: const Text(
              'No rooms in memory yet',
              key: Key('caregiver-rooms-empty'),
              textAlign: TextAlign.center,
              style: TextStyle(color: PatientTheme.ivory300),
            ),
          )
        else
          ..._rooms.map(
            (room) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Container(
                decoration: PatientTheme.insetCard(),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Container(
                      padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
                      decoration: const BoxDecoration(
                        color: PatientTheme.surfaceCard,
                        borderRadius: BorderRadius.vertical(
                          top: Radius.circular(PatientTheme.radius),
                        ),
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.meeting_room_outlined,
                            size: 18,
                            color: PatientTheme.ochre,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              (room['label'] as String?) ?? 'Room',
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                color: PatientTheme.ivory,
                              ),
                            ),
                          ),
                          if (room['room_id'] is int)
                            IconButton(
                              key: Key(
                                'caregiver-rename-${room['room_id']}',
                              ),
                              tooltip: 'Rename room',
                              onPressed: () => _rename(room),
                              icon: const Icon(Icons.edit_outlined, size: 16),
                            ),
                        ],
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'ANCHORS',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 1,
                              color: PatientTheme.ochre,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Wrap(
                            spacing: 6,
                            runSpacing: 6,
                            children: _labels(room['anchors'])
                                .map(
                                  (label) => Chip(
                                    key: ValueKey('anchor-$label'),
                                    label: Text(
                                      label,
                                      style: const TextStyle(fontSize: 11),
                                    ),
                                    visualDensity: VisualDensity.compact,
                                    side: const BorderSide(
                                      color: PatientTheme.borderStrong,
                                    ),
                                  ),
                                )
                                .toList(),
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            'OBJECTS',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 1,
                              color: PatientTheme.ochre,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Wrap(
                            spacing: 6,
                            runSpacing: 6,
                            children: _labels(room['objects'])
                                .map(
                                  (label) => Chip(
                                    key: ValueKey('object-$label'),
                                    label: Text(
                                      label,
                                      style: const TextStyle(fontSize: 11),
                                    ),
                                    visualDensity: VisualDensity.compact,
                                  ),
                                )
                                .toList(),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// System Status: only values the gateway actually reports. Nothing invented.
class StatusTab extends StatefulWidget {
  final ApiService apiService;

  const StatusTab({super.key, required this.apiService});

  @override
  State<StatusTab> createState() => _StatusTabState();
}

class _StatusTabState extends State<StatusTab> {
  Map<String, dynamic>? _health;
  Map<String, dynamic>? _capture;
  bool? _online;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final health = await widget.apiService.health();
      final online = await widget.apiService.isServerLive();
      Map<String, dynamic>? capture;
      try {
        capture = await widget.apiService.captureStatus();
      } on ApiException {
        capture = null;
      }
      if (!mounted) return;
      setState(() {
        _health = health;
        _online = online;
        _capture = capture;
      });
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  String get _captureLabel {
    final capture = _capture;
    if (capture == null || capture['available'] != true) return 'Not available';
    final status = capture['status'] as String? ?? 'unknown';
    final paused = capture['paused'] == true;
    return paused ? '$status (paused)' : status;
  }

  String get _lastInput {
    final capture = _capture;
    final at = capture?['last_frame_at'] as String?;
    if (at != null && at.isNotEmpty) return at;
    return 'Not reported by gateway';
  }

  @override
  Widget build(BuildContext context) {
    final health = _health;
    if (health == null) {
      return Center(
        child: Text(
          _error ?? 'Loading status…',
          key: const Key('caregiver-status-loading'),
          style: const TextStyle(color: PatientTheme.ivory300),
        ),
      );
    }

    final memory = <MapEntry<String, String>>[
      MapEntry('Dataset', (health['dataset_loaded'] as String?) ?? '-'),
      MapEntry('Scene graph ready', '${health['scene_graph_ready'] ?? false}'),
      MapEntry('Anchors', '${health['num_anchors'] ?? 0}'),
      MapEntry('Rooms', '${health['num_rooms'] ?? 0}'),
      MapEntry('Events', '${health['num_events'] ?? 0}'),
      MapEntry('Timeline frames', '${health['total_timeline_frames'] ?? 0}'),
    ];
    final system = <MapEntry<String, String>>[
      MapEntry('Internet status', _online == true ? 'Connected' : 'Disconnected'),
      MapEntry('Currently live', _captureLabel),
      MapEntry('Last video input', _lastInput),
      const MapEntry('Querying model', 'Aegis deterministic (no LLM)'),
      const MapEntry('LLM credits', 'N/A — no generative model'),
      MapEntry('API version', (health['version'] as String?) ?? '-'),
      const MapEntry('Memory capacity', 'Not reported by gateway'),
    ];

    Widget section(String title, List<MapEntry<String, String>> rows) => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 1,
                color: PatientTheme.ochre,
              ),
            ),
            const SizedBox(height: 8),
            ...rows.map(
              (row) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: PatientTheme.insetCard(),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          row.key,
                          style: const TextStyle(
                            fontSize: 13,
                            color: PatientTheme.ivory300,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Flexible(
                        child: Text(
                          row.value,
                          textAlign: TextAlign.right,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: PatientTheme.ivory,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        );

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
      children: [
        Row(
          children: [
            const Text(
              'System Status',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: PatientTheme.ivory,
              ),
            ),
            const Spacer(),
            IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
          ],
        ),
        const SizedBox(height: 16),
        section('MEMORY', memory),
        const SizedBox(height: 18),
        section('SYSTEM', system),
      ],
    );
  }
}
