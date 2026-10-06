class OpenAiCompatibleEndpoint {
  static Uri chatCompletionsUri(String baseUrl) {
    final parsed = Uri.tryParse(baseUrl.trim());
    if (parsed == null ||
        parsed.host.isEmpty ||
        parsed.userInfo.isNotEmpty ||
        parsed.hasQuery ||
        parsed.hasFragment) {
      throw const FormatException(
          'Enter a valid OpenAI-compatible API base URL.');
    }

    if (parsed.scheme != 'https') {
      throw const FormatException('Use an HTTPS API URL.');
    }

    final path = parsed.path.replaceFirst(RegExp(r'/+$'), '');
    final endpointPath =
        path.endsWith('/chat/completions') ? path : '$path/chat/completions';
    return parsed.replace(
        path: endpointPath.isEmpty ? '/chat/completions' : endpointPath);
  }
}
