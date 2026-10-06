import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services/aria_prompt_service.dart';
import '../services/openai_compatible_endpoint.dart';
import '../services/settings_service.dart';
import '../widgets/app_drawer.dart';

class AriaScreen extends StatefulWidget {
  const AriaScreen({super.key});
  @override
  State<AriaScreen> createState() => _AriaScreenState();
}

class _AriaScreenState extends State<AriaScreen> {
  final _input = TextEditingController();
  final _scrollController = ScrollController();
  final List<_Message> _messages = [
    _Message(
        text:
            "Hey! I'm ARIA — AutoReach's Intelligent Assistant. I'm here to help you get the most out of AutoReach — whether that's finding leads, setting up Resend for email, configuring your API keys, or using the Android app. What can I help you with? 🚀",
        isAria: true),
  ];
  bool _loading = false;

  static const _suggestions = [
    'How do I install AutoReach?',
    'How do I get a Google Maps API key?',
    'How do I set up Resend for emails?',
    'How many emails can I send per day?',
    'How does email scraping work?',
  ];

  final List<Map<String, String>> _history = [];

  Future<void> _send(String text) async {
    if (text.trim().isEmpty || _loading) return;
    _input.clear();
    setState(() {
      _messages.add(_Message(text: text.trim(), isAria: false));
      _loading = true;
    });
    _scrollToBottom();

    try {
      final apiKey = (await SettingsService.getAriaApiKey()).trim();
      final apiBaseUrl = await SettingsService.getAriaApiBaseUrl();
      final model = (await SettingsService.getAriaModel()).trim();
      final customPrompt = await SettingsService.getAriaCustomPrompt();
      final promptError = AriaPromptService.validateCustomPrompt(customPrompt);
      if (promptError != null) throw Exception(promptError);
      if (apiKey.isEmpty) {
        setState(() {
          _messages.add(_Message(
              text: 'Add your provider API key in Settings to use ARIA.',
              isAria: true));
          _loading = false;
        });
        _scrollToBottom();
        return;
      }
      if (model.isEmpty) throw Exception('Enter a model ID in Settings.');
      final headers = <String, String>{'Content-Type': 'application/json'};
      headers['Authorization'] = 'Bearer $apiKey';
      final res = await http
          .post(
            OpenAiCompatibleEndpoint.chatCompletionsUri(apiBaseUrl),
            headers: headers,
            body: jsonEncode({
              'model': model,
              'messages': [
                {
                  'role': 'system',
                  'content': AriaPromptService.buildSystemPrompt(customPrompt)
                },
                ..._history.reversed.take(8).toList().reversed,
                {'role': 'user', 'content': text.trim()},
              ],
              'temperature': 0.6,
              'max_completion_tokens': 400,
            }),
          )
          .timeout(const Duration(seconds: 30));
      final responseData = jsonDecode(res.body) as Map<String, dynamic>;
      if (res.statusCode < 200 || res.statusCode >= 300) {
        final errorData = responseData['error'];
        final message = errorData is Map ? errorData['message'] : null;
        throw Exception(message ??
            'The selected provider returned HTTP ${res.statusCode}.');
      }
      final choices = responseData['choices'] as List?;
      final responseMessage = choices?.isNotEmpty == true
          ? choices!.first['message'] as Map?
          : null;
      final reply = responseMessage?['content'] as String?;
      if (reply == null || reply.isEmpty)
        throw Exception('The selected provider returned an empty response.');
      if (AriaPromptService.containsProfanity(reply)) {
        throw Exception(
            'The response was blocked because it contained inappropriate language. Try again.');
      }
      _history.add({'role': 'user', 'content': text.trim()});
      _history.add({'role': 'assistant', 'content': reply});
      setState(() {
        _messages.add(_Message(text: reply, isAria: true));
        _loading = false;
      });
    } catch (error) {
      final message = error.toString().replaceFirst('Exception: ', '');
      setState(() {
        _messages.add(_Message(
            text: 'ARIA could not get a response: $message', isAria: true));
        _loading = false;
      });
    }
    _scrollToBottom();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(_scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(15),
              gradient: const LinearGradient(
                  colors: [Color(0xFF4ECDC4), Color(0xFF6C63FF)]),
            ),
            child: const Center(
                child: Text('A',
                    style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                        fontSize: 14))),
          ),
          const SizedBox(width: 10),
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('ARIA',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
              Text('AutoReach Assistant',
                  style: TextStyle(fontSize: 10, color: Color(0xFF4ECDC4))),
            ],
          ),
        ]),
      ),
      drawer: const AppDrawer(),
      body: Column(
        children: [
          // Suggestions
          SizedBox(
            height: 44,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              itemCount: _suggestions.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (_, i) => GestureDetector(
                onTap: () => _send(_suggestions[i]),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFF4ECDC4).withOpacity(0.08),
                    border: Border.all(
                        color: const Color(0xFF4ECDC4).withOpacity(0.25)),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(_suggestions[i],
                      style: const TextStyle(
                          color: Color(0xFF4ECDC4), fontSize: 11)),
                ),
              ),
            ),
          ),
          const Divider(height: 1, color: Color(0xFF2A2A3E)),
          // Messages
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length + (_loading ? 1 : 0),
              itemBuilder: (_, i) {
                if (i == _messages.length) return const _TypingIndicator();
                return _MessageBubble(message: _messages[i]);
              },
            ),
          ),
          // Input
          Container(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 16),
            decoration: const BoxDecoration(
              color: Color(0xFF1E1E2E),
              border: Border(top: BorderSide(color: Color(0xFF2A2A3E))),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _input,
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                    decoration: InputDecoration(
                      hintText: 'Ask ARIA anything about AutoReach...',
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 10),
                      border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide:
                              const BorderSide(color: Color(0xFF4ECDC4))),
                    ),
                    onSubmitted: _send,
                  ),
                ),
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: _loading ? null : () => _send(_input.text),
                  child: Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: const LinearGradient(
                          colors: [Color(0xFF4ECDC4), Color(0xFF6C63FF)]),
                      boxShadow: [
                        BoxShadow(
                            color: const Color(0xFF4ECDC4).withOpacity(0.3),
                            blurRadius: 8)
                      ],
                    ),
                    child: const Icon(Icons.send_rounded,
                        color: Colors.white, size: 18),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Message {
  final String text;
  final bool isAria;
  _Message({required this.text, required this.isAria});
}

class _MessageBubble extends StatelessWidget {
  final _Message message;
  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment:
            message.isAria ? MainAxisAlignment.start : MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (message.isAria) ...[
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                    colors: [Color(0xFF4ECDC4), Color(0xFF6C63FF)]),
              ),
              child: const Center(
                  child: Text('A',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.bold))),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: message.isAria
                    ? const Color(0xFF4ECDC4).withOpacity(0.08)
                    : const Color(0xFF6C63FF).withOpacity(0.15),
                border: Border.all(
                    color: message.isAria
                        ? const Color(0xFF4ECDC4).withOpacity(0.2)
                        : const Color(0xFF6C63FF).withOpacity(0.3)),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(14),
                  topRight: const Radius.circular(14),
                  bottomLeft: Radius.circular(message.isAria ? 4 : 14),
                  bottomRight: Radius.circular(message.isAria ? 14 : 4),
                ),
              ),
              child: Text(message.text,
                  style: const TextStyle(
                      color: Color(0xFFCDD6F4), fontSize: 13, height: 1.6)),
            ),
          ),
          if (!message.isAria) const SizedBox(width: 8),
        ],
      ),
    );
  }
}

class _TypingIndicator extends StatefulWidget {
  const _TypingIndicator();
  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1200))
      ..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const LinearGradient(
                  colors: [Color(0xFF4ECDC4), Color(0xFF6C63FF)])),
          child: const Center(
              child: Text('A',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.bold))),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: const Color(0xFF4ECDC4).withOpacity(0.08),
            border: Border.all(color: const Color(0xFF4ECDC4).withOpacity(0.2)),
            borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(14),
                topRight: Radius.circular(14),
                bottomRight: Radius.circular(14),
                bottomLeft: Radius.circular(4)),
          ),
          child: Row(
            children: List.generate(
                3,
                (i) => AnimatedBuilder(
                      animation: _ctrl,
                      builder: (_, __) {
                        final offset = ((_ctrl.value * 3) - i).clamp(0.0, 1.0);
                        final bounce =
                            offset < 0.5 ? offset * 2 : (1 - offset) * 2;
                        return Container(
                          margin: const EdgeInsets.symmetric(horizontal: 2),
                          width: 7,
                          height: 7,
                          decoration: const BoxDecoration(
                              color: Color(0xFF4ECDC4), shape: BoxShape.circle),
                          transform:
                              Matrix4.translationValues(0, -5 * bounce, 0),
                        );
                      },
                    )),
          ),
        ),
      ],
    );
  }
}
