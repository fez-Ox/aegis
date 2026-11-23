import 'package:flutter/material.dart';

import '../models/object_tile.dart';
import '../services/voice_service.dart';
import '../theme/app_theme.dart';
import '../widgets/object_icon.dart';

/// Caregiver Home: voice/text search and quick object cards. The cards come
/// from the server's tracked objects; nothing is hard-coded.
class CaregiverHomeTab extends StatefulWidget {
  final VoiceService voiceService;
  final List<ObjectTile> tiles;
  final ValueChanged<String> onAsk;
  final ValueChanged<ObjectTile> onTile;

  const CaregiverHomeTab({
    super.key,
    required this.voiceService,
    required this.tiles,
    required this.onAsk,
    required this.onTile,
  });

  @override
  State<CaregiverHomeTab> createState() => _CaregiverHomeTabState();
}

class _CaregiverHomeTabState extends State<CaregiverHomeTab>
    with TickerProviderStateMixin {
  final _controller = TextEditingController();
  late final AnimationController _ripple;
  bool _listening = false;
  String _micText = 'Tap microphone to speak';

  @override
  void initState() {
    super.initState();
    _ripple = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    );
  }

  @override
  void dispose() {
    _ripple.dispose();
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    widget.onAsk(text);
  }

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
          _controller.clear();
          widget.onAsk(words);
        }
      },
      onStatus: (status) {
        if (status == 'done' || status == 'notListening') _setListening(false);
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

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
      children: [
        Column(
          children: [
            SizedBox(
              width: 140,
              height: 140,
              child: AnimatedBuilder(
                animation: _ripple,
                builder: (context, child) {
                  return Stack(
                    alignment: Alignment.center,
                    children: [
                      if (_listening) ...[
                        _ring(_ripple.value, 0.30),
                        _ring((_ripple.value + 0.5) % 1.0, 0.20),
                      ],
                      SizedBox(
                        width: 96,
                        height: 96,
                        child: FilledButton(
                          key: const Key('caregiver-voice-mic'),
                          onPressed: _toggleVoice,
                          style: FilledButton.styleFrom(
                            shape: const CircleBorder(),
                            padding: EdgeInsets.zero,
                            backgroundColor: PatientTheme.ochre,
                            foregroundColor: PatientTheme.canvas,
                          ),
                          child: Icon(
                            _listening ? Icons.stop : Icons.mic,
                            size: 36,
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
            const SizedBox(height: 10),
            Text(
              _micText,
              key: const Key('caregiver-mic-status'),
              style: const TextStyle(fontSize: 12, color: PatientTheme.ivory300),
            ),
          ],
        ),
        const SizedBox(height: 20),
        Row(
          children: [
            Expanded(
              child: TextField(
                key: const Key('caregiver-search-field'),
                controller: _controller,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _submit(),
                style: const TextStyle(color: PatientTheme.ivory, fontSize: 16),
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search, color: PatientTheme.ochre),
                  hintText: 'Ask about the patient’s things…',
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 48,
              height: 48,
              child: FilledButton(
                key: const Key('caregiver-search-send'),
                onPressed: _submit,
                style: FilledButton.styleFrom(
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                  padding: EdgeInsets.zero,
                ),
                child: const Icon(Icons.arrow_forward),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 4),
          child: Text(
            'You can add a time: “Where were his keys yesterday?”',
            style: TextStyle(fontSize: 12, color: PatientTheme.ivory400),
          ),
        ),
        const SizedBox(height: 24),
        const Row(
          children: [
            Text(
              'Objects in memory',
              style: TextStyle(fontSize: 14, color: PatientTheme.ivory300),
            ),
            SizedBox(width: 12),
            Expanded(child: Divider(color: PatientTheme.border)),
          ],
        ),
        const SizedBox(height: 16),
        if (widget.tiles.isEmpty)
          Container(
            padding: const EdgeInsets.all(24),
            decoration: PatientTheme.insetCard(),
            child: const Text(
              'No objects in memory yet',
              key: Key('caregiver-no-objects'),
              textAlign: TextAlign.center,
              style: TextStyle(color: PatientTheme.ivory300),
            ),
          )
        else
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: widget.tiles.length,
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 14,
              mainAxisSpacing: 14,
              childAspectRatio: 1.25,
            ),
            itemBuilder: (context, index) {
              final tile = widget.tiles[index];
              return _TileButton(tile: tile, onTap: () => widget.onTile(tile));
            },
          ),
      ],
    );
  }
  Widget _ring(double value, double opacity) {
    return Transform.scale(
      scale: 0.95 + 0.33 * value,
      child: Container(
        width: 96,
        height: 96,
        decoration: BoxDecoration(
          color: PatientTheme.ochre.withValues(alpha: opacity * (1 - value)),
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}

class _TileButton extends StatelessWidget {
  final ObjectTile tile;
  final VoidCallback onTap;

  const _TileButton({required this.tile, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: PatientTheme.surfaceCard,
      borderRadius: BorderRadius.circular(PatientTheme.radius),
      child: InkWell(
        key: Key('caregiver-object-${tile.label.toLowerCase().replaceAll(' ', '-')}'),
        onTap: onTap,
        borderRadius: BorderRadius.circular(PatientTheme.radius),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(PatientTheme.radius),
            border: Border.all(color: PatientTheme.border),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                iconFor(tile.kind),
                size: 30,
                color: PatientTheme.ochre,
              ),
              const SizedBox(height: 8),
              Text(
                tile.label,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 14,
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
