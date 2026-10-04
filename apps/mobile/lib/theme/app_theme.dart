import 'package:flutter/material.dart';

class AppTheme {
  // Medical & Dementia-Accessible Palette
  static const Color darkCanvas = Color(0xFF0F172A);      // Slate Charcoal
  static const Color darkSurface = Color(0xFF1E293B);     // Slate Surface
  static const Color lightCanvas = Color(0xFFF8FAFC);     // Medical Porcelain
  static const Color lightSurface = Color(0xFFFFFFFF);    // Pure White Card

  static const Color primaryTeal = Color(0xFF0D9488);     // Therapeutic Teal
  static const Color tealAccent = Color(0xFF14B8A6);      // Bright Teal
  static const Color royalAmethyst = Color(0xFF6366F1);   // Anchor Purple
  static const Color alertAmber = Color(0xFFF59E0B);      // Calm Amber Attention
  static const Color textHighContrast = Color(0xFFF8FAFC); // WCAG AAA
  static const Color textMuted = Color(0xFF94A3B8);

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: darkCanvas,
      colorScheme: const ColorScheme.dark(
        primary: primaryTeal,
        secondary: royalAmethyst,
        surface: darkSurface,
        onSurface: textHighContrast,
        onPrimary: Colors.white,
      ),
      cardTheme: CardThemeData(
        color: darkSurface,
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: Color(0xFF334155), width: 1.5),
        ),
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(
          fontSize: 26,
          fontWeight: FontWeight.bold,
          color: textHighContrast,
          letterSpacing: -0.5,
        ),
        titleLarge: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: textHighContrast,
        ),
        bodyLarge: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w500,
          color: textHighContrast,
          height: 1.4,
        ),
        bodyMedium: TextStyle(
          fontSize: 16,
          color: textMuted,
        ),
      ),
    );
  }
}
