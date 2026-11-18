import { useState } from "react";
import Explain from "./Explain";

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

      <main>{view === "explain" ? <Explain /> : <h2>Drills</h2>}</main>

      <footer>
        Latin word data from Wiktionary (English Wiktionary contributors, CC
        BY-SA 4.0 and GFDL), extracted by Wiktextract and distributed via
        kaikki.org. Tatu Ylonen, "Wiktextract: Wiktionary as Machine-Readable
        Structured Data", Proceedings of LREC 2022, pp. 1317-1325. The database
        built from it is also CC BY-SA 4.0.
      </footer>
    </>
  );
}

export default App;
