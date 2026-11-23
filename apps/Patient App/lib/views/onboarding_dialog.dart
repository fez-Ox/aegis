import 'package:flutter/material.dart';

import '../models/patient_profile.dart';
import '../theme/app_theme.dart';

/// First-run setup. The caregiver phone number is required — the call button
/// cannot be used until it has been entered once.
class OnboardingDialog extends StatefulWidget {
  final PatientProfile initial;
  final ValueChanged<PatientProfile> onSaved;

  const OnboardingDialog({
    super.key,
    required this.initial,
    required this.onSaved,
  });

  @override
  State<OnboardingDialog> createState() => _OnboardingDialogState();
}

class _OnboardingDialogState extends State<OnboardingDialog> {
  late final TextEditingController _patient;
  late final TextEditingController _caregiver;
  late final TextEditingController _phone;
  late final TextEditingController _relationship;

  @override
  void initState() {
    super.initState();
    _patient = TextEditingController(text: widget.initial.patientName);
    _caregiver = TextEditingController(text: widget.initial.caregiverName);
    _phone = TextEditingController(text: widget.initial.caregiverPhone);
    _relationship = TextEditingController(text: widget.initial.relationship);
  }

  @override
  void dispose() {
    _patient.dispose();
    _caregiver.dispose();
    _phone.dispose();
    _relationship.dispose();
    super.dispose();
  }

  void _save() {
    final phone = _phone.text.trim();
    if (phone.isEmpty) return;
    widget.onSaved(widget.initial.copyWith(
      patientName: _patient.text.trim().isEmpty
          ? PatientProfile.defaultPatientName
          : _patient.text.trim(),
      caregiverName: _caregiver.text.trim().isEmpty
          ? PatientProfile.defaultCaregiverName
          : _caregiver.text.trim(),
      caregiverPhone: phone,
      relationship: _relationship.text.trim().isEmpty
          ? PatientProfile.defaultRelationship
          : _relationship.text.trim(),
    ));
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
              const Icon(
                Icons.phone_in_talk_rounded,
                size: 38,
                color: PatientTheme.ochre,
              ),
              const SizedBox(height: 12),
              const Text(
                'One quick setup',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                  color: PatientTheme.ivory,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Add the number of the person you can call for help. '
                'You can change it any time on the Call screen.',
                style: TextStyle(
                  fontSize: 14,
                  color: PatientTheme.ivory300,
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 20),
              _field(
                label: 'Your name',
                controller: _patient,
                hint: 'Arthur',
              ),
              const SizedBox(height: 14),
              _field(
                label: 'Caregiver name',
                controller: _caregiver,
                hint: 'Sarah',
              ),
              const SizedBox(height: 14),
              _field(
                label: 'Relationship',
                controller: _relationship,
                hint: 'Your daughter · Caretaker',
              ),
              const SizedBox(height: 14),
              _field(
                label: 'Caregiver phone number',
                controller: _phone,
                hint: '+1 555 010 2030',
                key: const Key('onboarding-phone'),
                keyboardType: TextInputType.phone,
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 22),
              SizedBox(
                height: 52,
                child: FilledButton(
                  key: const Key('onboarding-save'),
                  onPressed: _phone.text.trim().isEmpty ? null : _save,
                  child: const Text('Save and continue'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _field({
    required String label,
    required TextEditingController controller,
    required String hint,
    Key? key,
    TextInputType? keyboardType,
    ValueChanged<String>? onChanged,
  }) {
    return TextField(
      key: key,
      controller: controller,
      keyboardType: keyboardType,
      onChanged: onChanged,
      style: const TextStyle(color: PatientTheme.ivory, fontSize: 16),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        labelStyle: const TextStyle(color: PatientTheme.ochre, fontSize: 13),
      ),
    );
  }
}
