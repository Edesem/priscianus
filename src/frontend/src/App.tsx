import { useState } from "react";

type View = "explain" | "drills";

function App() {
  const [view, setView] = useState<View>("explain");

  return (
    <>
      <header>
        <h1>Priscianus</h1>
        <nav aria-label="Views">
          <button
            type="button"
            aria-pressed={view === "explain"}
            onClick={() => setView("explain")}
          >
            Explain
          </button>
          <button
            type="button"
            aria-pressed={view === "drills"}
            onClick={() => setView("drills")}
          >
            Drills
          </button>
        </nav>
      </header>

      <main>{view === "explain" ? <h2>Explain</h2> : <h2>Drills</h2>}</main>

      <footer>
        Latin word data from Wiktionary (English Wiktionary contributors), CC
        BY-SA 4.0, extracted with Wiktextract (kaikki.org). The database built
        from it is also CC BY-SA 4.0.
      </footer>
    </>
  );
}

export default App;
