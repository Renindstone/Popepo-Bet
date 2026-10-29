"use client";

import { type DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { ErrorNote } from "@/components/ui";
import { ApiError, upload } from "@/lib/api";
import type { Capture } from "@/lib/types";

const ACCEPT = ["image/png", "image/jpeg", "image/webp"];

function imagesFrom(list: FileList | null | undefined): File[] {
  return Array.from(list ?? []).filter((f) => ACCEPT.includes(f.type));
}

/**
 * Zona para subir capturas de cuotas: arrastrar, elegir archivo o pegar con Ctrl+V en cualquier parte
 * de la página. Cada imagen se sube en cuanto llega; la IA la lee en segundo plano.
 */
export function CaptureDrop({
  onUploaded,
  match,
  bookmaker,
  note,
  compact = false,
}: {
  onUploaded: (c: Capture) => void;
  match?: string;
  bookmaker?: string;
  note?: string;
  compact?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);

  const send = useCallback(
    async (files: File[]) => {
      if (!files.length) {
        setError(new ApiError(400, "Solo se admiten imágenes PNG, JPG o WEBP."));
        return;
      }
      setError(null);
      for (const file of files) {
        setBusy((n) => n + 1);
        const form = new FormData();
        form.append("file", file);
        if (match) form.append("match", match);
        if (bookmaker) form.append("bookmaker", bookmaker);
        if (note?.trim()) form.append("note", note.trim());
        try {
          onUploaded(await upload<Capture>("/captures", form));
        } catch (e) {
          setError(e as ApiError);
        } finally {
          setBusy((n) => n - 1);
        }
      }
    },
    [match, bookmaker, note, onUploaded],
  );

  // Pegar una captura con Ctrl+V en cualquier parte de la página
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      const files = imagesFrom(e.clipboardData?.files);
      if (files.length) {
        e.preventDefault();
        void send(files);
      }
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [send]);

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    void send(imagesFrom(e.dataTransfer.files));
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed text-center transition-colors ${
          dragging ? "border-boli bg-boli-suave" : "border-regla bg-hoja"
        } ${compact ? "px-4 py-5" : "px-5 py-10"}`}
      >
        <p className={`semi font-bold ${compact ? "text-base" : "text-lg"}`}>
          {busy > 0 ? "Subiendo…" : "Arrastra aquí la captura"}
        </p>
        <p className="mt-1 text-nota text-grafito">
          o pégala con <kbd className="border border-regla px-1 text-nota">Ctrl</kbd>+
          <kbd className="border border-regla px-1 text-nota">V</kbd> en esta página
        </p>
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={busy > 0}
          className="mt-3 inline-flex h-10 items-center border border-regla bg-papel px-4 text-interfaz font-semibold hover:border-grafito disabled:opacity-50"
        >
          Elegir imagen
        </button>
        <input
          ref={input}
          type="file"
          accept={ACCEPT.join(",")}
          multiple
          className="sr-only"
          tabIndex={-1}
          aria-label="Elegir captura de cuotas"
          onChange={(e) => {
            void send(imagesFrom(e.target.files));
            e.target.value = "";
          }}
        />
        {!compact && <p className="mt-3 text-nota text-grafito">PNG, JPG o WEBP de hasta 10 MB. Puedes subir varias.</p>}
      </div>
      {error && (
        <div className="mt-3">
          <ErrorNote error={error} />
        </div>
      )}
    </div>
  );
}
