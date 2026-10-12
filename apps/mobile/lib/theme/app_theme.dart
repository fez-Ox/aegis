import 'package:flutter/material.dart';

class AppTheme {
  // Warmer Tones Palette (Yellow & Off-White) - Dementia-Accessible
  static const Color darkCanvas = Color(0xFFFAF7F0);      // Warm Off-White Canvas / Linen
  static const Color darkSurface = Color(0xFFFFFFFF);     // Warm Off-White Card Surface
  static const Color lightCanvas = Color(0xFFFAF7F0);     // Warm Off-White Canvas
  static const Color lightSurface = Color(0xFFFFFFFF);    // Pure Warm White Card

  static const Color primaryTeal = Color(0xFFD97706);     // Warm Amber / Golden Honey
  static const Color tealAccent = Color(0xFFEAB308);      // Bright Warm Yellow
  static const Color royalAmethyst = Color(0xFFCA8A04);   // Warm Golden Ochre
  static const Color alertAmber = Color(0xFFF59E0B);      // Calm Amber Attention
  static const Color textHighContrast = Color(0xFF1C1917); // Deep Warm Charcoal (WCAG AAA)
  static const Color textMuted = Color(0xFF78716C);       // Warm Muted Stone
  static const Color cardBorder = Color(0xFFE7E0D3);      // Warm Subtle Border

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: darkCanvas,
      colorScheme: const ColorScheme.light(
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
          side: const BorderSide(color: cardBorder, width: 1.5),
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
