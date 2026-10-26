export async function GET() {
  return Response.json({
    service: "monter-studio",
    version: "0.1.0",
    status: "ok",
    architecture: "local-bridge-plus-web-studio",
  });
}
