import 'package:flutter/material.dart';

import '../models/patient_profile.dart';
import '../services/call_service.dart';
import '../theme/app_theme.dart';

/// The Call tab. The caregiver number is set once at first launch and can be
/// edited here later. The call itself uses the device dialer.
class CallView extends StatefulWidget {
  final PatientProfile profile;
  final CallService callService;
  final VoidCallback onBack;
  final VoidCallback onEditNumber;

  const CallView({
    super.key,
    required this.profile,
    required this.callService,
    required this.onBack,
    required this.onEditNumber,
  });

  @override
  State<CallView> createState() => _CallViewState();
}

class _CallViewState extends State<CallView> {
  bool _busy = false;

  Future<void> _call() async {
    setState(() => _busy = true);
    await widget.callService.call(widget.profile.caregiverPhone);
    if (!mounted) return;
    setState(() => _busy = false);
  }

  Future<void> _message() async {
    setState(() => _busy = true);
    // The check-in text is fixed; only the button label is generic.
    await widget.callService.message(
      widget.profile.caregiverPhone,
      'please check on me',
    );
    if (!mounted) return;
    setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final name = widget.profile.caregiverName;
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
      children: [
        const Text(
          'Need a hand?',
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.w700,
            color: PatientTheme.ivory,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'You are safe at home. $name is always happy to help.',
          style: const TextStyle(fontSize: 14, color: PatientTheme.ivory300),
        ),
        const SizedBox(height: 20),
        Container(
          padding: const EdgeInsets.all(20),
          decoration: PatientTheme.insetCard(color: PatientTheme.surfaceCard),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: PatientTheme.emeraldSurface,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: PatientTheme.emerald),
                  ),
                  child: const Text(
                    'AVAILABLE NEARBY',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: PatientTheme.emerald,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Text(
                name,
                style: const TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w700,
                  color: PatientTheme.ivory,
                ),
              ),
              Text(
                widget.profile.relationship,
                style: const TextStyle(fontSize: 14, color: PatientTheme.ivory400),
              ),
              const SizedBox(height: 20),
              SizedBox(
                height: 52,
                child: FilledButton.icon(
                  key: const Key('call-now'),
                  onPressed: _busy ? null : _call,
                  icon: const Icon(Icons.call),
                  label: Text('Call $name now'),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                height: 48,
                child: OutlinedButton.icon(
                  key: const Key('message-caregiver'),
                  onPressed: _busy ? null : _message,
                  icon: const Icon(Icons.message_outlined, size: 18),
                  label: const Text('Send Message'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: PatientTheme.ivory300,
                    side: const BorderSide(color: PatientTheme.borderStrong),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                height: PatientTheme.touchTarget,
                child: TextButton(
                  key: const Key('edit-caregiver'),
                  onPressed: widget.onEditNumber,
                  child: const Text('Change caregiver or number'),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        SizedBox(
          height: 52,
          child: FilledButton(
            onPressed: widget.onBack,
            child: const Text('Back to home'),
          ),
        ),
      ],
    );
  }
}
