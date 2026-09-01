import { useCallback, useEffect, useState } from "react";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { ImagePlus, LogIn, LogOut, Search, ShieldCheck, Sparkles, X } from "lucide-react";
import { apiScope } from "./auth";

type Mode = "keyword" | "vector" | "hybrid" | "semantic" | "image" | "combined";
type Product = { id: string; name: string; description: string; category: string; image_url: string | null; score: number | null };
type Response = { results: Product[]; diagnostics: { mode: Mode; count: number; elapsed_ms: number } };

function useAccessToken() {
  // Acquire per-request tokens silently; MSAL handles interactive sign-in at the page level.
  const { instance, accounts } = useMsal();
  return useCallback(async () => {
    const account = accounts[0];
    if (!account) throw new Error("Sign in is required");
    return (await instance.acquireTokenSilent({ account, scopes: [apiScope] })).accessToken;
  }, [accounts, instance]);
}

function ProductImage({ product, token }: { product: Product; token: () => Promise<string> }) {
  // Images are private, so fetch bytes with a bearer token instead of exposing Blob URLs.
  const [source, setSource] = useState<string>();
  useEffect(() => {
    let objectUrl: string | undefined;
    if (!product.image_url) {
      setSource(undefined);
      return;
    }
    const imageUrl = product.image_url;
    token().then((accessToken) => fetch(imageUrl, { headers: { Authorization: `Bearer ${accessToken}` } }))
      .then((response) => { if (!response.ok) throw new Error(); return response.blob(); })
      .then((blob) => { objectUrl = URL.createObjectURL(blob); setSource(objectUrl); })
      .catch(() => setSource(undefined));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [product.image_url, token]);
  return source ? <img src={source} alt={product.name} /> : <div className="image-fallback"><Sparkles size={24} /></div>;
}

export default function App() {
  // The selected mode determines whether the API receives text, an image, or both.
  const authenticated = useIsAuthenticated();
  const { instance, accounts } = useMsal();
  const token = useAccessToken();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("hybrid");
  const [imageDataUrl, setImageDataUrl] = useState<string>();
  const [imageName, setImageName] = useState("");
  const [data, setData] = useState<Response>();
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  function selectImage(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 4 * 1024 * 1024) {
      setErrorMessage("Images must be JPEG, PNG, or WebP under 4 MiB.");
      setStatus("error");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setImageDataUrl(String(reader.result));
      setImageName(file.name);
      setData(undefined);
      setErrorMessage("");
      setStatus("idle");
    };
    reader.onerror = () => {
      setErrorMessage("The selected image could not be read.");
      setStatus("error");
    };
    reader.readAsDataURL(file);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const needsImage = mode === "image" || mode === "combined";
    const needsText = mode !== "image";
    if ((needsText && !query.trim()) || (needsImage && !imageDataUrl) || query.length > 200) return;
    setData(undefined);
    setErrorMessage("");
    setStatus("loading");
    try {
      const accessToken = await token();
      const response = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ query, mode, top: 12, imageDataUrl: needsImage ? imageDataUrl : undefined }) });
      if (!response.ok) throw new Error(`Search failed (${response.status})`);
      setData(await response.json());
      setStatus("idle");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Search could not be completed.");
      setStatus("error");
    }
  }

  return <main>
    <header>
      <div className="brand"><span>TJX</span><strong>Product Lens</strong></div>
      {authenticated ? <div className="account"><span>{accounts[0]?.name}</span><button className="icon" title="Sign out" onClick={() => instance.logoutRedirect()}><LogOut size={18} /></button></div> : <button onClick={() => instance.loginRedirect({ scopes: [apiScope] })}><LogIn size={18} /> Sign in</button>}
    </header>
    <section className="workspace">
      <div className="heading"><div><p className="eyebrow">PRIVATE CATALOG</p><h1>Find the product, not the filename.</h1></div><ShieldCheck aria-label="Protected catalog" size={28} /></div>
      <form onSubmit={submit}>
        <div className="modes" aria-label="Search mode">{(["keyword", "vector", "hybrid", "semantic", "image", "combined"] as Mode[]).map((value) => <button type="button" className={mode === value ? "active" : ""} onClick={() => { setMode(value); setData(undefined); }} key={value}>{value}</button>)}</div>
        {(mode === "image" || mode === "combined") && <div className="image-query"><label><ImagePlus size={18} /><span>{imageDataUrl ? "Replace image" : "Choose image"}</span><input type="file" accept="image/jpeg,image/png,image/webp" onChange={selectImage} disabled={!authenticated} /></label>{imageDataUrl && <div className="image-selection"><img src={imageDataUrl} alt="Search reference" /><span>{imageName}</span><button type="button" className="icon" title="Remove image" onClick={() => { setImageDataUrl(undefined); setImageName(""); setData(undefined); }}><X size={17} /></button></div>}</div>}
        <div className="query"><Search size={22} /><input value={query} onChange={(event) => setQuery(event.target.value)} maxLength={200} placeholder={mode === "image" ? "Image search" : mode === "combined" ? "Add color, category, or style constraints" : "Search color, material, shape, or category"} aria-label="Product search" disabled={!authenticated || mode === "image"} /><button disabled={!authenticated || status === "loading" || ((mode === "image" || mode === "combined") && !imageDataUrl)}>{status === "loading" ? "Searching" : "Search"}</button></div>
      </form>
      {status === "loading" && <div className="state" role="status">Understanding the request and searching the private catalog...</div>}
      {status === "error" && <div className="state error" role="alert">{errorMessage}</div>}
      {!authenticated && <div className="state">Sign in to search the private catalog.</div>}
      {authenticated && data?.results.length === 0 && <div className="state">No matching products found.</div>}
      {data && <><div className="diagnostics"><span>{data.diagnostics.count} results</span><span>{data.diagnostics.mode}</span><span>{data.diagnostics.elapsed_ms} ms</span></div><div className="grid">{data.results.map((product) => <article key={product.id}><ProductImage product={product} token={token} /><div className="product-copy"><p>{product.category}</p><h2>{product.name}</h2><span>{product.description}</span>{product.score !== null && <small>Relevance {product.score.toFixed(3)}</small>}</div></article>)}</div></>}
    </section>
  </main>;
}