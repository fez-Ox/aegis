import 'dart:async';

import 'package:flutter/material.dart';

import '../models/memory_answer.dart';
import '../models/object_tile.dart';
import '../models/patient_profile.dart';
import '../services/api_service.dart';
import '../services/call_service.dart';
import '../services/preferences_service.dart';
import '../services/voice_service.dart';
import '../theme/app_theme.dart';
import '../widgets/object_icon.dart';
import 'answer_drawer.dart';
import 'call_view.dart';
import 'onboarding_dialog.dart';

/// The patient app's single screen: ask from the patient's perspective, tap a
/// picture to locate, and call the caregiver. Built from Patient App/patient.html.
class PatientHome extends StatefulWidget {
  final ApiService apiService;
  final VoiceService voiceService;
  final CallService callService;
  final PreferencesService preferencesService;

  const PatientHome({
    super.key,
    required this.apiService,
    required this.voiceService,
    required this.callService,
    required this.preferencesService,
  });

  @override
  State<PatientHome> createState() => _PatientHomeState();
}

class _PatientHomeState extends State<PatientHome> with TickerProviderStateMixin {
  final _controller = TextEditingController();
  late final AnimationController _ripple;

  PatientProfile _profile = const PatientProfile();
  MemoryAnswer? _answer;
  ObjectKind _answerKind = ObjectKind.keys;
  bool _drawerOpen = false;
  bool _loading = false;
  String? _error;
  bool _listening = false;
  String _micText = 'Tap microphone to speak';
  int _tab = 0;
  List<ObjectTile> _tiles = const [];
  bool _serverLive = false;
  Timer? _healthTimer;

  @override
  void initState() {
    super.initState();
    _ripple = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    );
    _loadProfile();
    _loadTiles();
    _checkServer();
    _healthTimer = Timer.periodic(
      const Duration(seconds: 10),
      (_) => _checkServer(),
    );
  }

  Future<void> _checkServer() async {
    final live = await widget.apiService.isServerLive();
    if (!mounted) return;
    setState(() => _serverLive = live);
    // Tiles are server-backed and must follow the graph, including a graph
    // that appears after the app was opened.
    if (live) await _loadTiles();
  }

  Future<void> _loadTiles() async {
    final labels = await widget.apiService.trackedObjects();
    if (!mounted) return;
    setState(() => _tiles = labels.map(ObjectTile.fromServerLabel).toList());
  }

  Future<void> _loadProfile() async {
    final profile = await widget.preferencesService.load();
    final serverUrl = await widget.preferencesService.loadServerUrl();
    if (!mounted) return;
    if (serverUrl != null && serverUrl.isNotEmpty) {
      widget.apiService.setBaseUrl(serverUrl);
    }
    setState(() => _profile = profile);
    if (!profile.isConfigured) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _showOnboarding());
    }
  }

  @override
  void dispose() {
    _healthTimer?.cancel();
    _controller.dispose();
    _ripple.dispose();
    widget.voiceService.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------- querying

  Future<void> _submit({String? text}) async {
    final query = (text ?? _controller.text).trim();
    if (query.isEmpty || _loading) return;
    _controller.clear();
    await _run(() => widget.apiService.ask(query), ObjectKind.mug);
    _lastQuestion = query;
  }

  Future<void> _locate(ObjectTile tile) async {
    await _run(
      () => widget.apiService.lookupObject(tile.label),
      tile.kind,
    );
    _lastQuestion = tile.question;
  }

  Future<void> _run(
    Future<MemoryAnswer> Function() action,
    ObjectKind kind,
  ) async {
    setState(() {
      _loading = true;
      _error = null;
      _drawerOpen = false;
    });
    try {
      final answer = await action();
      if (!mounted) return;
      setState(() {
        _answer = answer;
        _answerKind = kind;
        _drawerOpen = true;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = ApiService.unreachableMessage);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _lastQuestion = '';

  Future<void> _recall(TimeCue cue) async {
    final question = _lastQuestion.isEmpty ? _answer?.title ?? '' : _lastQuestion;
    if (question.isEmpty) return;
    final answer = await widget.apiService.recall(question, cue: cue);
    if (!mounted) return;
    setState(() {
      _answer = answer;
      _drawerOpen = true;
    });
  }

  // ------------------------------------------------------------------- voice

  Future<void> _toggleVoice() async {
    if (_listening) {
      await widget.voiceService.stop();
      _setListening(false);
      return;
    }
    final started = await widget.voiceService.start(
      onWords: (words, finalResult) {
        if (!mounted) return;
        setState(() => _controller.text = words);
        if (finalResult && words.trim().isNotEmpty) {
          widget.voiceService.stop();
          _setListening(false);
          _submit(text: words);
        }
      },
      onStatus: (status) {
        if (!mounted) return;
        if (status == 'done' || status == 'notListening') {
          _setListening(false);
        }
      },
    );
    if (!mounted) return;
    if (started) {
      _setListening(true);
    } else {
      setState(() => _micText = 'Voice search unavailable — please type');
    }
  }

  void _setListening(bool value) {
    if (!mounted) return;
    setState(() {
      _listening = value;
      _micText = value ? 'Listening... Speak naturally' : 'Tap microphone to speak';
    });
    if (value) {
      _ripple.repeat();
    } else {
      _ripple.stop();
    }
  }

  // ----------------------------------------------------------------- profile

  Future<void> _showOnboarding() async {
    final saved = await showDialog<PatientProfile>(
      context: context,
      barrierDismissible: false,
      builder: (_) => OnboardingDialog(
        initial: _profile,
        onSaved: (profile) => Navigator.of(context).pop(profile),
      ),
    );
    if (saved == null) return;
    await widget.preferencesService.save(saved);
    if (!mounted) return;
    setState(() => _profile = saved);
  }

  Future<void> _editName() async {
    final name = TextEditingController(text: _profile.patientName);
    final saved = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: PatientTheme.surfaceCard,
        title: const Text(
          'Set patient name',
          style: TextStyle(color: PatientTheme.ivory, fontSize: 18),
        ),
        content: TextField(
          key: const Key('patient-name-field'),
          controller: name,
          autofocus: true,
          style: const TextStyle(color: PatientTheme.ivory),
          decoration: const InputDecoration(hintText: 'e.g., Arthur'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('patient-name-save'),
            onPressed: () => Navigator.pop(context, name.text.trim()),
            child: const Text('Save name'),
          ),
        ],
      ),
    );
    name.dispose();
    if (saved == null || saved.isEmpty) return;
    final updated = _profile.copyWith(patientName: saved);
    await widget.preferencesService.save(updated);
    if (mounted) setState(() => _profile = updated);
  }

  /// Change the API server without rebuilding — essential for a demo where the
  /// phone is on Wi-Fi/cellular, not connected by USB.
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
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Use the deployed link, or http://<laptop-IP>:8000 on the same Wi-Fi.',
              style: TextStyle(
                color: PatientTheme.ivory300,
                fontSize: 13,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('server-url-field'),
              controller: url,
              autofocus: true,
              style: const TextStyle(color: PatientTheme.ivory, fontSize: 14),
              decoration: const InputDecoration(hintText: 'https://…'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('server-url-save'),
            onPressed: () => Navigator.pop(context, url.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (saved == null || saved.isEmpty) return;
    widget.apiService.setBaseUrl(saved);
    await widget.preferencesService.saveServerUrl(saved);
    if (mounted) {
      setState(() => _error = null);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Memory server updated')),
      );
    }
  }

  // -------------------------------------------------------------------- build

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PatientTheme.canvas,
      body: Stack(
        children: [
          SafeArea(
            child: Column(
              children: [
                _buildHeader(),
                Expanded(
                  child: IndexedStack(
                    index: _tab,
                    children: [
                      _buildHome(),
                      CallView(
                        profile: _profile,
                        callService: widget.callService,
                        onBack: () => setState(() => _tab = 0),
                        onEditNumber: _showOnboarding,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (_drawerOpen && _answer != null) _buildDrawerOverlay(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 14),
      decoration: const BoxDecoration(
        color: PatientTheme.surfaceRaised,
        border: Border(
          bottom: BorderSide(color: PatientTheme.border),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'PATIENT PERSPECTIVE',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1,
                    color: PatientTheme.ochre,
                  ),
                ),
                const SizedBox(height: 6),
                Text.rich(
                  TextSpan(
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: PatientTheme.ivory,
                    ),
                    children: [
                      const TextSpan(text: 'Ask from '),
                      WidgetSpan(
                        alignment: PlaceholderAlignment.baseline,
                        baseline: TextBaseline.alphabetic,
                        child: GestureDetector(
                          key: const Key('edit-patient-name'),
                          onTap: _editName,
                          child: Text(
                            '${_profile.patientName}’s',
                            style: const TextStyle(
                              color: PatientTheme.ochre,
                              decoration: TextDecoration.underline,
                              decorationStyle: TextDecorationStyle.dotted,
                            ),
                          ),
                        ),
                      ),
                      const TextSpan(text: ' perspective'),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: PatientTheme.touchTarget,
                    height: PatientTheme.touchTarget,
                    child: IconButton(
                      key: const Key('open-server-settings'),
                      tooltip: 'Memory server',
                      onPressed: _editServer,
                      icon: const Icon(Icons.settings_outlined, size: 22),
                      style: IconButton.styleFrom(
                        backgroundColor: PatientTheme.surfaceCard,
                        foregroundColor: PatientTheme.ochre,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(
                    height: 52,
                    child: FilledButton.icon(
                      key: const Key('open-call'),
                      onPressed: () => setState(() => _tab = 1),
                      icon: const Icon(Icons.call, size: 22),
                      label: const Text('Call'),
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 20),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              _ServerBadge(live: _serverLive),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHome() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
      children: [
        _buildMicHero(),
        const SizedBox(height: 24),
        _buildSearchBar(),
        const SizedBox(height: 8),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 4),
          child: Text(
            'You can add a time: “Where were my keys yesterday?”',
            style: TextStyle(fontSize: 12, color: PatientTheme.ivory400),
          ),
        ),
        if (_error != null) ...[
          const SizedBox(height: 16),
          _buildError(),
        ],
        const SizedBox(height: 24),
        const Row(
          children: [
            Text(
              'Or tap a picture to locate',
              style: TextStyle(fontSize: 14, color: PatientTheme.ivory300),
            ),
            SizedBox(width: 12),
            Expanded(child: Divider(color: PatientTheme.border)),
          ],
        ),
        const SizedBox(height: 16),
        _buildObjectGrid(),
      ],
    );
  }

  Widget _buildMicHero() {
    return Column(
      children: [
        SizedBox(
          width: 140,
          height: 140,
          child: AnimatedBuilder(
            animation: _ripple,
            builder: (context, child) {
              final value = _ripple.value;
              return Stack(
                alignment: Alignment.center,
                children: [
                  if (_listening) ...[
                    _rippleCircle(value, 0.30),
                    _rippleCircle((value + 0.5) % 1.0, 0.20),
                  ],
                  Container(
                    width: 128,
                    height: 128,
                    decoration: BoxDecoration(
                      color: PatientTheme.ochre.withValues(alpha: 0.10),
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: PatientTheme.ochre.withValues(alpha: 0.25),
                      ),
                    ),
                  ),
                  SizedBox(
                    width: 96,
                    height: 96,
                    child: FilledButton(
                      key: const Key('voice-mic'),
                      onPressed: _toggleVoice,
                      style: FilledButton.styleFrom(
                        shape: const CircleBorder(),
                        padding: EdgeInsets.zero,
                        backgroundColor: PatientTheme.ochre,
                        foregroundColor: PatientTheme.canvas,
                      ),
                      child: Icon(
                        _listening ? Icons.stop : Icons.mic,
                        size: 40,
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
        const SizedBox(height: 12),
        Text(
          _micText,
          key: const Key('mic-status'),
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: _listening ? PatientTheme.ochre : PatientTheme.ivory300,
          ),
        ),
      ],
    );
  }

  Widget _rippleCircle(double value, double opacity) {
    final scale = 0.95 + 0.33 * value;
    return Transform.scale(
      scale: scale,
      child: Container(
        width: 128,
        height: 128,
        decoration: BoxDecoration(
          color: PatientTheme.ochre.withValues(alpha: opacity * (1 - value)),
          shape: BoxShape.circle,
        ),
      ),
    );
  }

  Widget _buildSearchBar() {
    return Row(
      children: [
        Expanded(
          child: TextField(
            key: const Key('ask-field'),
            controller: _controller,
            textInputAction: TextInputAction.send,
            onSubmitted: (_) => _submit(),
            style: const TextStyle(color: PatientTheme.ivory, fontSize: 16),
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search, color: PatientTheme.ochre),
              hintText: 'Try: Where is my mug?',
            ),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 48,
          height: 48,
          child: FilledButton(
            key: const Key('ask-send'),
            onPressed: _loading ? null : () => _submit(),
            style: FilledButton.styleFrom(
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
              ),
              padding: EdgeInsets.zero,
            ),
            child: _loading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: PatientTheme.canvas,
                    ),
                  )
                : const Icon(Icons.arrow_forward),
          ),
        ),
      ],
    );
  }

  Widget _buildObjectGrid() {
    if (_tiles.isEmpty) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(24),
        decoration: PatientTheme.insetCard(),
        child: const Column(
          children: [
            Icon(Icons.inventory_2_outlined, size: 32, color: PatientTheme.ivory400),
            SizedBox(height: 10),
            Text(
              'No objects in memory yet',
              key: Key('no-objects'),
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 15, color: PatientTheme.ivory300),
            ),
          ],
        ),
      );
    }
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: _tiles.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 14,
        mainAxisSpacing: 14,
        childAspectRatio: 1.25,
      ),
      itemBuilder: (context, index) {
        final tile = _tiles[index];
        return _ObjectButton(tile: tile, onTap: () => _locate(tile));
      },
    );
  }

  Widget _buildError() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: PatientTheme.insetCard(),
      child: Row(
        children: [
          const Icon(Icons.wifi_off, color: PatientTheme.ivory400),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _error!,
              key: const Key('unreachable-message'),
              style: const TextStyle(color: PatientTheme.ivory, fontSize: 14),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDrawerOverlay() {
    return Stack(
      children: [
        Positioned.fill(
          child: GestureDetector(
            key: const Key('answer-scrim'),
            onTap: () => setState(() => _drawerOpen = false),
            child: Container(color: PatientTheme.canvas.withValues(alpha: 0.75)),
          ),
        ),
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: Container(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.92,
            ),
            decoration: const BoxDecoration(
              color: PatientTheme.surfaceCard,
              borderRadius: BorderRadius.vertical(
                top: Radius.circular(PatientTheme.radiusLarge),
              ),
              border: Border(
                top: BorderSide(color: PatientTheme.borderStrong),
              ),
            ),
            child: AnswerDrawer(
              answer: _answer!,
              kind: _answerKind,
              onTimeCue: _recall,
              onClose: () => setState(() => _drawerOpen = false),
            ),
          ),
        ),
      ],
    );
  }
}

class _ObjectButton extends StatelessWidget {
  final ObjectTile tile;
  final VoidCallback onTap;

  const _ObjectButton({required this.tile, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: PatientTheme.surfaceCard,
      borderRadius: BorderRadius.circular(PatientTheme.radius),
      child: InkWell(
        key: Key('object-${tile.label.toLowerCase().replaceAll(' ', '-')}'),
        onTap: onTap,
        borderRadius: BorderRadius.circular(PatientTheme.radius),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(PatientTheme.radius),
            border: Border.all(color: PatientTheme.border),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(14),
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: toneFor(tile.kind),
                  ),
                  border: Border.all(
                    color: PatientTheme.ochre.withValues(alpha: 0.35),
                  ),
                ),
                child: Icon(
                  iconFor(tile.kind),
                  color: PatientTheme.ochre,
                  size: 28,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                tile.label,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: PatientTheme.ivory,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Small status pill: green when the memory server answers, red otherwise.
class _ServerBadge extends StatelessWidget {
  final bool live;

  const _ServerBadge({required this.live});

  @override
  Widget build(BuildContext context) {
    final color = live ? PatientTheme.emerald : Colors.redAccent;
    return Container(
      key: const Key('server-status'),
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 4),
          Text(
            live ? 'LIVE' : 'NOT LIVE',
            style: TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.5,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
