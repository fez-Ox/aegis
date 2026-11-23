import 'package:flutter/material.dart';

import '../models/patient_profile.dart';
import '../theme/app_theme.dart';

/// First-run setup: the caregiver tells the app whose perspective to present
/// and which server to read. Both are stored on-device only.
class OnboardingDialog extends StatefulWidget {
  final PatientProfile initial;
  final String serverUrl;
  final ValueChanged<PatientProfile> onSaved;
  final ValueChanged<String> onServerSaved;

  const OnboardingDialog({
    super.key,
    required this.initial,
    required this.serverUrl,
    required this.onSaved,
    required this.onServerSaved,
  });

  @override
  State<OnboardingDialog> createState() => _OnboardingDialogState();
}

class _OnboardingDialogState extends State<OnboardingDialog> {
  late final TextEditingController _name;
  late final TextEditingController _server;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.initial.patientName);
    _server = TextEditingController(text: widget.serverUrl);
  }

  @override
  void dispose() {
    // Kept alive until the dialog is fully gone; popping with a result can
    // rebuild the route once more, so disposing here would be premature.
    super.dispose();
  }

  void _save() {
    final name = _name.text.trim();
    if (name.isEmpty) return;
    widget.onServerSaved(_server.text.trim());
    widget.onSaved(widget.initial.copyWith(patientName: name));
  }

  @override
  Widget build(BuildContext context) {
    return PopScope<PatientProfile>(
      canPop: false,
      child: Dialog(
        backgroundColor: PatientTheme.surfaceCard,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(PatientTheme.radiusLarge),
          side: const BorderSide(color: PatientTheme.borderStrong),
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(22, 24, 22, 22),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(Icons.visibility_outlined,
                  size: 38, color: PatientTheme.ochre),
              const SizedBox(height: 12),
              const Text(
                'Set up caregiver view',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                  color: PatientTheme.ivory,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Whose memory are you viewing, and where is the Aegis server?',
                style: TextStyle(
                  fontSize: 14,
                  color: PatientTheme.ivory300,
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 20),
              TextField(
                key: const Key('caregiver-patient-name'),
                controller: _name,
                autofocus: true,
                onChanged: (_) => setState(() {}),
                style: const TextStyle(color: PatientTheme.ivory, fontSize: 16),
                decoration: const InputDecoration(labelText: "Patient's name"),
              ),
              const SizedBox(height: 14),
              TextField(
                key: const Key('caregiver-server-url'),
                controller: _server,
                style: const TextStyle(color: PatientTheme.ivory, fontSize: 14),
                decoration: const InputDecoration(
                  labelText: 'Memory server URL',
                  hintText: 'https://…',
                ),
              ),
              const SizedBox(height: 22),
              SizedBox(
                height: 52,
                child: FilledButton(
                  key: const Key('caregiver-setup-save'),
                  onPressed: _name.text.trim().isEmpty ? null : _save,
                  child: const Text('Save and continue'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
