import 'dart:async';

import 'package:flutter/material.dart';

import '../models/memory_answer.dart';
import '../models/object_tile.dart';
import '../models/patient_profile.dart';
import '../models/search_entry.dart';
import '../services/api_service.dart';
import '../services/call_service.dart';
import '../services/history_service.dart';
import '../services/preferences_service.dart';
import '../services/voice_service.dart';
import '../theme/app_theme.dart';
import 'answer_drawer.dart';
import 'caregiver_tabs.dart';
import 'home_tab.dart';
import 'onboarding_dialog.dart';

/// Caregiver shell: header, four tabs, answer drawer and first-run setup.
class CaregiverHome extends StatefulWidget {
  final ApiService apiService;
  final VoiceService voiceService;
  final HistoryService historyService;
  final PreferencesService preferencesService;
  final CallService callService;

  const CaregiverHome({
    super.key,
    required this.apiService,
    required this.voiceService,
    required this.historyService,
    required this.preferencesService,
    required this.callService,
  });

  @override
  State<CaregiverHome> createState() => _CaregiverHomeState();
}

class _CaregiverHomeState extends State<CaregiverHome> {
  static const _tabs = ['Home', 'Track', 'Interior', 'Status'];

  PatientProfile _profile = const PatientProfile();
  List<ObjectTile> _tiles = const [];
  List<SearchEntry> _history = const [];
  MemoryAnswer? _answer;
  ObjectKind _answerKind = ObjectKind.other;
  bool _drawerOpen = false;
  bool _loading = false;
  bool _serverLive = false;
  String? _error;
  int _tab = 0;
  int _interactionRequest = 0;
  Timer? _healthTimer;
  String _lastQuestion = '';

  @override
  void initState() {
    super.initState();
    _loadProfile();
    _loadTiles();
    _loadHistory();
    _checkServer();
    _healthTimer = Timer.periodic(
      const Duration(seconds: 10),
      (_) => _checkServer(),
    );
  }

  @override
  void dispose() {
    _healthTimer?.cancel();
    widget.voiceService.dispose();
    super.dispose();
  }

  Future<void> _checkServer() async {
    final live = await widget.apiService.isServerLive();
    if (!mounted) return;
    setState(() => _serverLive = live);
    // Keep the object cards in sync with the graph on the server.
    if (live) await _loadTiles();
  }

  Future<void> _loadProfile() async {
    final profile = await widget.preferencesService.load();
    if (!mounted) return;
    setState(() => _profile = profile);
    // Caregiver needs a patient name on first launch, like the patient app
    // needs a caregiver number.
    if (profile.patientName.isEmpty ||
        profile.patientName == PatientProfile.defaultPatientName) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _showOnboarding());
    }
  }

  Future<void> _loadTiles() async {
    final labels = await widget.apiService.trackedObjects();
    if (!mounted) return;
    setState(() => _tiles = labels.map(ObjectTile.fromServerLabel).toList());
  }

  Future<void> _loadHistory() async {
    final entries = await widget.historyService.load();
    if (mounted) setState(() => _history = entries);
  }

  Future<void> _showOnboarding() async {
    await showDialog<PatientProfile>(
      context: context,
      barrierDismissible: false,
      builder: (_) => OnboardingDialog(
        initial: _profile,
        serverUrl: widget.apiService.baseUrl,
        onSaved: (profile) async {
          await widget.preferencesService.save(profile);
          if (!mounted) return;
          setState(() => _profile = profile);
          if (Navigator.of(context).canPop()) Navigator.of(context).pop();
        },
        onServerSaved: (url) {
          widget.apiService.setBaseUrl(url);
          widget.preferencesService.saveServerUrl(url);
          _loadTiles();
          _checkServer();
        },
      ),
    );
  }

  Future<void> _editName() async {
    final name = TextEditingController(text: _profile.patientName);
    final saved = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: PatientTheme.surfaceCard,
        title: const Text(
          "Patient's name",
          style: TextStyle(color: PatientTheme.ivory, fontSize: 18),
        ),
        content: TextField(
          key: const Key('caregiver-name-field'),
          controller: name,
          autofocus: true,
          style: const TextStyle(color: PatientTheme.ivory),
          decoration: const InputDecoration(hintText: 'Arthur'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('caregiver-name-save'),
            onPressed: () => Navigator.pop(context, name.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (saved == null || saved.isEmpty) return;
    final updated = _profile.copyWith(patientName: saved);
    await widget.preferencesService.save(updated);
    if (mounted) setState(() => _profile = updated);
  }

  Future<void> _editServer() async {
    final url = TextEditingController(text: widget.apiService.baseUrl);
    final saved = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: PatientTheme.surfaceCard,
        title: const Text(
          'Memory server',
          style: TextStyle(color: PatientTheme.ivory, fontSize: 18),
        ),
        content: TextField(
          key: const Key('caregiver-server-field'),
          controller: url,
          autofocus: true,
          style: const TextStyle(color: PatientTheme.ivory, fontSize: 14),
          decoration: const InputDecoration(hintText: 'https://…'),
        ),
        actions: [
          TextButton(
            key: const Key('caregiver-server-default'),
            onPressed: () =>
                Navigator.pop(context, ApiService.defaultBaseUrl),
            child: const Text('Use default'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('caregiver-server-save'),
            onPressed: () => Navigator.pop(context, url.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (saved == null || saved.isEmpty) return;
    widget.apiService.setBaseUrl(saved);
    await widget.preferencesService.saveServerUrl(saved);
    _loadTiles();
    _checkServer();
  }

  // ---------------------------------------------------------------- querying

  Future<void> _ask(String text) async {
    if (text.trim().isEmpty || _loading) return;
    _lastQuestion = text.trim();
    setState(() {
      _loading = true;
      _error = null;
      _drawerOpen = false;
    });
    try {
      final answer = await widget.apiService.ask(_lastQuestion);
      if (!mounted) return;
      setState(() {
        _answer = answer;
        _answerKind = _kindFor(_lastQuestion);
        _drawerOpen = true;
        _loading = false;
      });
      await _record(_lastQuestion, answer);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  Future<void> _locate(ObjectTile tile) async {
    await _ask('Where is my ${tile.label.toLowerCase()}?');
    _lastQuestion = 'Where is my ${tile.label.toLowerCase()}?';
  }

  Future<void> _recall(TimeCue cue) async {
    final question = _lastQuestion;
    if (question.isEmpty) return;
    final answer = await widget.apiService.recall(question, cue: cue);
    if (!mounted) return;
    setState(() {
      _answer = answer;
      _drawerOpen = true;
    });
    await _record(question, answer);
  }

  Future<void> _record(String question, MemoryAnswer answer) async {
    final entry = SearchEntry(
      query: question,
      answer: answer.found ? answer.summary : answer.summary,
      at: DateTime.now().toIso8601String(),
      mode: answer.mode.name,
      ambiguous: answer.mode == ResolutionMode.ambiguous,
      candidates: answer.candidates.map((c) => c.place).toList(),
    );
    final entries = await widget.historyService.add(entry);
    if (mounted) setState(() => _history = entries);
  }

  ObjectKind _kindFor(String question) {
    final lower = question.toLowerCase();
    for (final tile in _tiles) {
      if (lower.contains(tile.label.toLowerCase())) return tile.kind;
    }
    return ObjectKind.other;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PatientTheme.canvas,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            if (_error != null)
              Container(
                width: double.infinity,
                color: PatientTheme.surfaceCard,
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                child: Text(
                  _error!,
                  key: const Key('caregiver-error'),
                  style: const TextStyle(color: Colors.redAccent, fontSize: 12),
                ),
              ),
            Expanded(
              child: IndexedStack(
                index: _tab,
                children: [
                  CaregiverHomeTab(
                    voiceService: widget.voiceService,
                    tiles: _tiles,
                    onAsk: _ask,
                    onTile: _locate,
                  ),
                  TrackingTab(
                    apiService: widget.apiService,
                    tiles: _tiles,
                    interactionRequest: _interactionRequest,
                  ),
                  InteriorTab(apiService: widget.apiService, tiles: _tiles),
                  StatusTab(apiService: widget.apiService),
                  SearchHistoryTab(entries: _history),
                ],
              ),
            ),
            _buildBottomNav(),
          ],
        ),
      ),
      floatingActionButton: _drawerOpen && _answer != null
          ? null
          : null,
      bottomSheet: _drawerOpen && _answer != null
          ? _buildDrawer()
          : null,
    );
  }

  Widget _buildHeader() {
    final statusColor =
        _serverLive ? PatientTheme.emerald : Colors.redAccent;
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 12),
      decoration: const BoxDecoration(
        color: PatientTheme.surfaceRaised,
        border: Border(bottom: BorderSide(color: PatientTheme.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'CAREGIVER VIEW',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1,
                    color: PatientTheme.ochre,
                  ),
                ),
              ),
              if (_serverLive)
                Container(
                  margin: const EdgeInsets.only(right: 6),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: PatientTheme.emeraldSurface,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: PatientTheme.emerald),
                  ),
                  child: const Text(
                    'MEMORY ACTIVE',
                    style: TextStyle(
                      fontSize: 9,
                      fontWeight: FontWeight.w700,
                      color: PatientTheme.emerald,
                    ),
                  ),
                ),
              Container(
                key: const Key('caregiver-server-status'),
                padding:
                    const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: statusColor),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: statusColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _serverLive ? 'LIVE' : 'NOT LIVE',
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                        color: statusColor,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          GestureDetector(
            key: const Key('caregiver-edit-name'),
            onTap: _editName,
            child: Text.rich(
              TextSpan(
                style: const TextStyle(
                  fontSize: 19,
                  fontWeight: FontWeight.w700,
                  color: PatientTheme.ivory,
                ),
                children: [
                  const TextSpan(text: 'See from '),
                  TextSpan(
                    text: _profile.patientName,
                    style: const TextStyle(
                      color: PatientTheme.ochre,
                      decoration: TextDecoration.underline,
                      decorationStyle: TextDecorationStyle.dotted,
                    ),
                  ),
                  const TextSpan(text: "’s perspective"),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              SizedBox(
                width: PatientTheme.touchTarget,
                height: PatientTheme.touchTarget,
                child: IconButton(
                  key: const Key('caregiver-server-settings'),
                  tooltip: 'Memory server',
                  onPressed: _editServer,
                  icon: const Icon(Icons.settings_outlined, size: 20),
                  style: IconButton.styleFrom(
                    backgroundColor: PatientTheme.surfaceCard,
                    foregroundColor: PatientTheme.ochre,
                  ),
                ),
              ),
              if (_tab == 1) ...[
                const SizedBox(width: 8),
                SizedBox(
                  height: PatientTheme.touchTarget,
                  child: OutlinedButton.icon(
                    key: const Key('caregiver-interaction'),
                    onPressed: () => setState(() => _interactionRequest++),
                    icon: const Icon(Icons.bar_chart, size: 16),
                    label: const Text(
                      'Interaction',
                      style: TextStyle(fontSize: 12),
                    ),
                  ),
                ),
              ],
              const SizedBox(width: 8),
              SizedBox(
                height: PatientTheme.touchTarget,
                child: OutlinedButton.icon(
                  key: const Key('caregiver-view-history'),
                  onPressed: () => setState(() => _tab = 4),
                  icon: const Icon(Icons.history, size: 16),
                  label: const Text(
                    'History',
                    style: TextStyle(fontSize: 12),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBottomNav() {
    final icons = [
      Icons.home_outlined,
      Icons.track_changes_outlined,
      Icons.meeting_room_outlined,
      Icons.monitor_heart_outlined,
    ];
    return Container(
      decoration: const BoxDecoration(
        color: PatientTheme.surfaceRaised,
        border: Border(top: BorderSide(color: PatientTheme.border)),
      ),
      child: Row(
        children: List.generate(_tabs.length, (index) {
          final selected = index == _tab;
          return Expanded(
            child: SizedBox(
              height: 60,
              child: TextButton.icon(
                key: Key('caregiver-tab-$index'),
                onPressed: () => setState(() => _tab = index),
                icon: Icon(
                  icons[index],
                  size: 20,
                  color: selected ? PatientTheme.ochre : PatientTheme.ivory400,
                ),
                label: Text(
                  _tabs[index],
                  softWrap: false,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 10,
                    color: selected ? PatientTheme.ochre : PatientTheme.ivory400,
                  ),
                ),
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildDrawer() {
    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.85,
      ),
      decoration: const BoxDecoration(
        color: PatientTheme.surfaceCard,
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(PatientTheme.radiusLarge),
        ),
        border: Border(top: BorderSide(color: PatientTheme.borderStrong)),
      ),
      child: AnswerDrawer(
        answer: _answer!,
        kind: _answerKind,
        onTimeCue: _recall,
        onClose: () => setState(() => _drawerOpen = false),
      ),
    );
  }
}

