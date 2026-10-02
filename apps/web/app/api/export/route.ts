import { NextRequest } from "next/server";
export async function GET(request: NextRequest) {
  const url = new URL(
    "/v1/exports/orders.csv",
    process.env.API_BASE_URL || "http://localhost:8000",
  );
  for (const key of ["gpu_model", "start", "end", "region"]) {
    const value = request.nextUrl.searchParams.get(key);
    if (value)
      url.searchParams.set(
        key,
        (key === "start" || key === "end") && /^\d{4}-\d{2}-\d{2}$/.test(value)
          ? `${value}T00:00:00Z`
          : value,
      );
  }
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok)
      return new Response("CSV export unavailable", { status: 502 });
    return new Response(response.body, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition":
          'attachment; filename="compute-market-orders.csv"',
      },
    });
  } catch {
    return new Response("API unavailable. CSV export could not be generated.", {
      status: 502,
    });
  }
}
