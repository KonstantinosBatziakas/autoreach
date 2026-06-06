export default async function handler(req, res) {
    // CORS — allow autoreach.dev and localhost
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') return res.status(200).end();
    if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

    const { message, history = [], system } = req.body;
    if (!message) return res.status(400).json({ error: 'No message' });

    const apiKey = process.env.GROQ_API_KEY;
    if (!apiKey) return res.status(500).json({ reply: 'ARIA is not configured.' });

    try {
        const groqRes = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify({
                model: 'llama-3.1-8b-instant',
                messages: [{ role: 'system', content: system }, ...history.slice(-8), { role: 'user', content: message }],
                temperature: 0.6,
                max_tokens: 400
            })
        });

        const data = await groqRes.json();
        if (!data.choices) {
            console.error('[ARIA] Groq error:', data);
            return res.status(500).json({ reply: 'ARIA is having trouble right now. Try again in a moment!' });
        }

        return res.status(200).json({ reply: data.choices[0].message.content });
    } catch (e) {
        console.error('[ARIA] Exception:', e);
        return res.status(500).json({ reply: "Can't reach ARIA right now. Try again in a moment!" });
    }
}
