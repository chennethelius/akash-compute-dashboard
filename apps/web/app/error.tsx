"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <div className="empty">
      <h2>This view could not be loaded.</h2>
      <p>Please try again in a moment.</p>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
