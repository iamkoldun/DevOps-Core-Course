const START_TIME = new Date().toISOString();

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const cf = request.cf as IncomingRequestCfProperties | undefined;

    console.log("request", JSON.stringify({
      method: request.method,
      path: url.pathname,
      colo: cf?.colo,
      country: cf?.country,
      asn: cf?.asn,
    }));

    if (url.pathname === "/health") {
      return json({ status: "ok", service: env.APP_NAME, uptimeSince: START_TIME });
    }

    if (url.pathname === "/") {
      return json({
        app: env.APP_NAME,
        course: env.COURSE_NAME,
        owner: env.OWNER,
        message: "Hello from Cloudflare Workers",
        timestamp: new Date().toISOString(),
        endpoints: ["/", "/health", "/edge", "/info", "/counter", "/settings"],
      });
    }

    if (url.pathname === "/edge") {
      return json({
        colo: cf?.colo ?? null,
        country: cf?.country ?? null,
        city: cf?.city ?? null,
        region: cf?.region ?? null,
        continent: cf?.continent ?? null,
        asn: cf?.asn ?? null,
        asOrganization: cf?.asOrganization ?? null,
        httpProtocol: cf?.httpProtocol ?? null,
        tlsVersion: cf?.tlsVersion ?? null,
        clientIp: request.headers.get("cf-connecting-ip"),
        userAgent: request.headers.get("user-agent"),
        timestamp: new Date().toISOString(),
      });
    }

    if (url.pathname === "/info") {
      return json({
        deployment: {
          app: env.APP_NAME,
          course: env.COURSE_NAME,
          owner: env.OWNER,
          relatedK8sService: env.RELATED_K8S_SERVICE,
        },
        runtime: "cloudflare-workers",
        bindings: {
          vars: ["APP_NAME", "COURSE_NAME", "OWNER", "RELATED_K8S_SERVICE"],
          secrets: ["API_TOKEN", "ADMIN_EMAIL"],
          kv: ["SETTINGS"],
        },
        timestamp: new Date().toISOString(),
      });
    }

    if (url.pathname === "/counter") {
      const raw = await env.SETTINGS.get("visits");
      const visits = Number(raw ?? "0") + 1;
      await env.SETTINGS.put("visits", String(visits));
      return json({ visits, key: "visits", binding: "SETTINGS" });
    }

    if (url.pathname === "/settings") {
      const auth = request.headers.get("authorization") ?? "";
      const expected = `Bearer ${env.API_TOKEN}`;
      if (auth !== expected) {
        console.log("unauthorized /settings access", { ip: request.headers.get("cf-connecting-ip") });
        return json({ error: "unauthorized" }, 401);
      }

      if (request.method === "GET") {
        const lastReleaseNote = await env.SETTINGS.get("release_note");
        return json({
          admin: env.ADMIN_EMAIL,
          lastReleaseNote: lastReleaseNote ?? null,
        });
      }

      if (request.method === "PUT") {
        const body = (await request.json().catch(() => ({}))) as { note?: string };
        if (!body.note) return json({ error: "missing 'note'" }, 400);
        await env.SETTINGS.put("release_note", body.note);
        return json({ stored: true, note: body.note });
      }

      return json({ error: "method not allowed" }, 405);
    }

    return json({ error: "not found", path: url.pathname }, 404);
  },
} satisfies ExportedHandler<Env>;
