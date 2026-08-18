# Agent keys

One file per agent, containing nothing but the key. A missing file means that
agent is never offered — there is no half-configured state.

    fast.key   Groq         https://console.groq.com/keys        gsk_...
    deep.key   OpenRouter   https://openrouter.ai/keys           sk-or-...
    wide.key   NVIDIA       https://build.nvidia.com             nvapi-...
    long.key   Gemini       https://aistudio.google.com/apikey   AIza...

All four are free and none requires a card.

**Cerebras is deliberately absent.** Its free credits need a payment method on
file and expire after 30 days — a metered account by another name. Most
"free LLM API" roundups list it as card-free; they are wrong.

Write keys ON THE SERVER, never through a chat window or a git commit:

    pct exec 101 -- sh -c 'umask 077; cat > /opt/orb/keys/fast.key'

The router re-reads the directory per request, so no restart is needed to add
or remove a key — only a model-ID change needs `docker compose up -d remote`.

## When an agent stops working

Check `/agents`. Each entry carries `last_error` and `disabled_reason`.

* `404 model_not_found` — the model ID was retired. These are env vars in
  docker-compose.yml; look up the provider's current catalogue and change it.
  Query the provider directly rather than trusting a blog post:

      curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $KEY"

* `401` / `403` — bad or revoked key.
* `402` — the account wants money. Drop that provider.
* `429` — rate limited. Transient; the agent stays available and that one
  request falls back to local.

Any of `401 402 403 404` withdraws the agent from the picker for 10 minutes so
it cannot silently serve local answers under a remote label.
