"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <div className="empty">
      <h2>This view could not be loaded.</h2>
      <p>Check the API connection and try again.</p>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
