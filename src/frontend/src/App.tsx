import { useEffect, useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, NavLink, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError, type ComparableBasis, type HistoryPoint, type Page, type PriceSummary, type ProductSearchItem, type ProductTicketAppearance, type SyncRun, type SyncStatus, type TicketSummary } from "./api/client";
import { useUiStore } from "./state/uiStore";

const navItems = [
  { to: "/tickets", label: "Tickets", hint: "Historial de compras" },
  { to: "/products", label: "Productos", hint: "Evolución de precios" },
  { to: "/sync", label: "Sincronización", hint: "Estado de importación" },
];

function formatCents(cents: number | null): string {
  if (cents === null) return "—";
  const sign = cents < 0 ? "-" : "";
  const absolute = Math.abs(cents);
  return sign + Math.floor(absolute / 100).toLocaleString("es-ES") + "," + String(absolute % 100).padStart(2, "0") + " €";
}
function formatDate(value: string | null): string {
  return value ? new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Madrid" }).format(new Date(value)) : "—";
}
function formatShortDate(value: string): string {
  return new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeZone: "Europe/Madrid" }).format(new Date(value));
}
function formatPercent(value: number | null): string {
  return value === null ? "No calculable" : (value > 0 ? "+" : "") + value.toFixed(2).replace(".", ",") + "%";
}
function basisLabel(basis: ComparableBasis | null): string { return basis === "kg" ? "€/kg" : "€/unidad"; }
function statusLabel(status: string): string {
  const labels: Record<string, string> = { ready: "Listo", partial: "Parcial", failed: "Fallido", needs_review: "Revisión", queued: "En cola", running: "En curso", succeeded: "Completada", manual: "Manual" };
  return labels[status] || status;
}
function statusClass(status: string): string {
  return status === "ready" || status === "succeeded" ? "status status-success" : status === "partial" || status === "needs_review" ? "status status-warning" : status === "failed" ? "status status-danger" : "status";
}
function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "TICKET_NOT_FOUND") return "No encontramos este ticket.";
    if (error.code === "PRODUCT_NOT_FOUND") return "No encontramos este producto.";
    if (error.code === "SYNC_ALREADY_RUNNING") return "Ya hay una sincronización en curso.";
    return error.message;
  }
  return "No se pudo conectar con el backend local.";
}

function StatusBadge({ status }: { status: string }) { return <span className={statusClass(status)}>{statusLabel(status)}</span>; }
function LoadingRows({ count = 5 }: { count?: number }) {
  return <div className="skeleton-list" aria-label="Cargando">{Array.from({ length: count }, (_, i) => <div className="skeleton-row" key={i} />)}</div>;
}
function ErrorState({ error, retry }: { error: unknown; retry: () => void }) {
  return <div className="state-panel state-error" role="alert"><span className="state-kicker">No disponible</span><h2>No pudimos cargar estos datos</h2><p>{errorMessage(error)}</p><button className="button button-secondary" type="button" onClick={retry}>Reintentar</button></div>;
}
function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return <div className="state-panel"><span className="state-kicker">Sin registros</span><h2>{title}</h2><p>{text}</p>{action}</div>;
}
function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (next: number) => void }) {
  if (totalPages <= 1) return null;
  return <nav className="pagination" aria-label="Paginación"><button className="button button-secondary" type="button" disabled={page <= 1} onClick={() => onChange(page - 1)}>Anterior</button><span aria-live="polite">Página <strong>{page}</strong> de <strong>{totalPages}</strong></span><button className="button button-secondary" type="button" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>Siguiente</button></nav>;
}
function PageIntro({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: ReactNode }) {
  return <header className="page-intro"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="intro-copy">{description}</p></div>{children ? <div className="intro-actions">{children}</div> : null}</header>;
}
function Breadcrumbs({ current, parent = { to: "/tickets", label: "Tickets" } }: { current: string; parent?: { to: string; label: string } }) {
  return <nav className="breadcrumbs" aria-label="Migas de pan"><Link to={parent.to}>{parent.label}</Link><span aria-hidden="true">/</span><span aria-current="page">{current}</span></nav>;
}

function TicketTable({ data }: { data: Page<TicketSummary> }) {
  const navigate = useNavigate();
  const open = (id: string) => navigate("/tickets/" + id);
  return <div className="table-frame"><table className="data-table"><caption className="sr-only">Tickets sincronizados</caption><thead><tr><th>Fecha</th><th>Líneas</th><th>Estado</th><th className="numeric">Total</th></tr></thead><tbody>{data.items.map((ticket) => <tr key={ticket.id} className="interactive-row" tabIndex={0} onClick={() => open(ticket.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(ticket.id); } }} aria-label={"Abrir ticket del " + formatDate(ticket.purchasedAt)}><td><span className="primary-cell">{formatDate(ticket.purchasedAt)}</span><span className="secondary-cell">{ticket.timezone}</span></td><td>{ticket.lineCount}</td><td><StatusBadge status={ticket.parseStatus} /></td><td className="numeric money">{formatCents(ticket.totalCents)}</td></tr>)}</tbody></table></div>;
}
function TicketsPage() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page") || "1") || 1);
  const query = useQuery({ queryKey: ["tickets", page], queryFn: ({ signal }) => api.listTickets(page, signal), retry: 1 });
  const changePage = (next: number) => setParams(next === 1 ? {} : { page: String(next) });
  return <section className="page-content"><PageIntro eyebrow="Registro de compra" title="Tickets" description="Tus compras, ordenadas por fecha, con el estado real de cada importación." />{query.isPending ? <LoadingRows /> : query.isError ? <ErrorState error={query.error} retry={() => { void query.refetch(); }} /> : query.data.totalItems === 0 ? <EmptyState title="Aún no hay tickets sincronizados" text="Cuando importes tu primer ticket aparecerá aquí." action={<Link className="button button-primary" to="/sync">Abrir sincronización</Link>} /> : <><div className="section-meta"><span>{query.data.totalItems} tickets</span><span>50 por página</span></div><TicketTable data={query.data} /><Pagination page={query.data.page} totalPages={query.data.totalPages} onChange={changePage} /></>}</section>;
}

function TicketDetailPage() {
  const { ticketId = "" } = useParams();
  const query = useQuery({ queryKey: ["ticket", ticketId], queryFn: ({ signal }) => api.getTicket(ticketId, signal), enabled: Boolean(ticketId), retry: false });
  if (query.isPending) return <section className="page-content"><Breadcrumbs current="Cargando" /><LoadingRows count={7} /></section>;
  if (query.isError) return <section className="page-content"><Breadcrumbs current="Ticket" /><ErrorState error={query.error} retry={() => { void query.refetch(); }} /></section>;
  const ticket = query.data;
  return <section className="page-content"><Breadcrumbs current={ticket.ticketNumber ? "Ticket " + ticket.ticketNumber : "Detalle"} /><PageIntro eyebrow="Detalle de compra" title={ticket.ticketNumber ? "Ticket " + ticket.ticketNumber : "Ticket"} description={formatDate(ticket.purchasedAt)}><div className="total-block"><span>Total</span><strong>{formatCents(ticket.totalCents)}</strong></div></PageIntro>{ticket.parseStatus !== "ready" ? <div className="notice notice-warning" role="status"><strong>Importación {statusLabel(ticket.parseStatus).toLowerCase()}.</strong> Algunas líneas pueden necesitar revisión.</div> : null}<div className="table-frame"><table className="data-table detail-table"><caption className="sr-only">Líneas del ticket</caption><thead><tr><th>Descripción</th><th>Cantidad / peso</th><th>Comparable</th><th className="numeric">Importe</th><th><span className="sr-only">Acción</span></th></tr></thead><tbody>{ticket.items.map((item) => <tr key={item.id}><td><span className="primary-cell">{item.rawDescription}</span>{item.parseStatus !== "ready" ? <span className="secondary-cell">{statusLabel(item.parseStatus)}</span> : null}</td><td>{item.weightGrams !== null ? item.weightGrams + " g" : item.quantity ? item.quantity + " " + item.quantityUnit : "—"}</td><td className="money">{item.comparablePriceCents !== null ? <><strong>{formatCents(item.comparablePriceCents)}</strong> <span className="basis-label">{basisLabel(item.comparableBasis)}</span></> : "No disponible"}</td><td className="numeric money">{formatCents(item.lineAmountCents)}</td><td>{item.product ? <Link className="text-link action-link" to={"/products/" + item.product.id}>Ver evolución<span className="sr-only"> de {item.product.name}</span></Link> : <span className="muted-small">Sin producto vinculado</span>}</td></tr>)}</tbody></table></div><div className="total-footer"><span>Total del ticket</span><strong className="money">{formatCents(ticket.totalCents)}</strong></div></section>;
}

function ProductCombobox() {
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");
  const [active, setActive] = useState(-1);
  const listId = useId();
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ["product-search", debounced], queryFn: ({ signal }) => api.searchProducts(debounced, signal), enabled: debounced.length >= 2, retry: 1 });
  useEffect(() => { const timer = window.setTimeout(() => { setDebounced(term.trim()); setActive(-1); }, 280); return () => window.clearTimeout(timer); }, [term]);
  const items = query.data?.items || [];
  const open = term.trim().length >= 2 && (query.isPending || query.isError || query.data !== undefined);
  const select = (item: ProductSearchItem) => { setTerm(item.name); setDebounced(""); navigate("/products/" + item.id); };
  const keyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!open) return;
    if (event.key === "ArrowDown") { event.preventDefault(); setActive((value) => Math.min(value + 1, items.length - 1)); }
    if (event.key === "ArrowUp") { event.preventDefault(); setActive((value) => Math.max(value - 1, 0)); }
    if (event.key === "Escape") { setActive(-1); setTerm(""); }
    if (event.key === "Enter" && active >= 0 && items[active]) { event.preventDefault(); select(items[active]); }
  };
  return <div className="search-block"><label htmlFor="product-search">Buscar producto</label><div className="combobox-wrap"><input id="product-search" className="search-input" type="search" role="combobox" value={term} onChange={(event) => setTerm(event.target.value)} onKeyDown={keyDown} aria-expanded={open} aria-controls={listId} aria-autocomplete="list" aria-activedescendant={active >= 0 ? listId + "-option-" + active : undefined} placeholder="Por ejemplo, tomate pera" />{open ? <div className="combobox-results">{query.isPending ? <p className="combobox-message">Buscando…</p> : query.isError ? <p className="combobox-message error-text">{errorMessage(query.error)}</p> : items.length === 0 ? <p className="combobox-message">No se encontraron productos</p> : <ul id={listId} role="listbox">{items.map((item, index) => <li id={listId + "-option-" + index} role="option" aria-selected={index === active} key={item.id} onMouseDown={(event) => { event.preventDefault(); select(item); }}><span>{item.name}</span><span className="basis-label">{basisLabel(item.basis)}</span></li>)}</ul>}</div> : null}</div><p className="helper-text">{term.length === 1 ? "Escribí al menos dos caracteres." : "Usá ↑ ↓ y Enter para elegir un producto."}</p></div>;
}
function ProductsPage() {
  return <section className="page-content"><PageIntro eyebrow="Catálogo comparable" title="Productos" description="Buscá una descripción canónica y separá siempre las series por unidad o por kilo." /><ProductCombobox /><div className="product-search-note"><strong>Precio comparable</strong><span>El backend calcula €/unidad o €/kg. La interfaz sólo muestra la base recibida.</span></div></section>;
}

function SummaryCards({ summary, basis }: { summary: PriceSummary; basis: ComparableBasis }) {
  return <div className="summary-grid"><div className="summary-card"><span>Último precio</span><strong className="money">{formatCents(summary.lastPriceCents)}</strong><small>{basisLabel(basis)}</small></div><div className="summary-card"><span>Variación</span><strong className={summary.changeCents !== null && summary.changeCents > 0 ? "money negative" : "money"}>{summary.changeCents === null ? "—" : formatCents(summary.changeCents)}</strong><small>{formatPercent(summary.changePercent)}</small></div><div className="summary-card"><span>Rango observado</span><strong className="money">{formatCents(summary.minimumPriceCents)} — {formatCents(summary.maximumPriceCents)}</strong><small>{summary.observationCount} observaciones</small></div></div>;
}
function HistoryChart({ points, basis }: { points: HistoryPoint[]; basis: ComparableBasis }) {
  const chartData = points.filter((point) => point.basis === basis).map((point) => ({ ...point, label: formatShortDate(point.purchasedAt), value: point.priceCents / 100 }));
  if (chartData.length === 0) return <EmptyState title="Sin observaciones válidas" text="Este producto todavía no tiene puntos comparables para graficar." />;
  return <div className="chart-panel"><div className="chart-heading"><div><span className="eyebrow">Serie {basisLabel(basis)}</span><h2>Historia de precio</h2></div><span className="chart-unit">{basisLabel(basis)}</span></div><div className="chart-wrap" aria-label={"Gráfica de evolución " + basisLabel(basis)}><ResponsiveContainer width="100%" height={260}><LineChart data={chartData} margin={{ top: 16, right: 12, left: 0, bottom: 8 }}><XAxis dataKey="label" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} tickFormatter={(value: number) => value + " €"} /><Tooltip formatter={(value: number) => [value.toFixed(2).replace(".", ",") + " €", basisLabel(basis)]} /><Line type="monotone" dataKey="value" stroke="#b54a2f" strokeWidth={3} dot={{ r: 4, fill: "#f7f2e8", stroke: "#b54a2f", strokeWidth: 2 }} /></LineChart></ResponsiveContainer></div><div className="table-frame chart-table"><table className="data-table"><caption>Datos de la gráfica, serie {basisLabel(basis)}</caption><thead><tr><th>Fecha</th><th>Precio comparable</th></tr></thead><tbody>{chartData.map((point, index) => <tr key={point.ticketId + "-" + index}><td>{point.label}</td><td className="money">{formatCents(point.priceCents)} <span className="basis-label">{basisLabel(point.basis)}</span></td></tr>)}</tbody></table></div></div>;
}
function ProductTicketsTable({ data }: { data: Page<ProductTicketAppearance> }) {
  return <div className="table-frame"><table className="data-table"><caption>Tickets donde aparece el producto</caption><thead><tr><th>Fecha</th><th>Precio comparable</th><th className="numeric">Importe línea</th></tr></thead><tbody>{data.items.map((item, index) => <tr key={item.ticketId + "-" + index}><td><Link className="text-link" to={"/tickets/" + item.ticketId}>{formatDate(item.purchasedAt)}</Link></td><td className="money">{formatCents(item.comparablePriceCents)} <span className="basis-label">{basisLabel(item.basis)}</span></td><td className="numeric money">{formatCents(item.lineAmountCents)}</td></tr>)}</tbody></table></div>;
}
function ProductDetailPage() {
  const { productId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page") || "1") || 1);
  const productQuery = useQuery({ queryKey: ["product", productId], queryFn: ({ signal }) => api.getProduct(productId, signal), enabled: Boolean(productId), retry: false });
  const ticketsQuery = useQuery({ queryKey: ["product-tickets", productId, page], queryFn: ({ signal }) => api.getProductTickets(productId, page, signal), enabled: Boolean(productId) && productQuery.isSuccess, retry: 1 });
  if (productQuery.isPending) return <section className="page-content"><Breadcrumbs current="Producto" parent={{ to: "/products", label: "Productos" }} /><LoadingRows count={6} /></section>;
  if (productQuery.isError) return <section className="page-content"><Breadcrumbs current="Producto" parent={{ to: "/products", label: "Productos" }} /><ErrorState error={productQuery.error} retry={() => { void productQuery.refetch(); }} /></section>;
  const product = productQuery.data;
  return <section className="page-content"><Breadcrumbs current={product.name} parent={{ to: "/products", label: "Productos" }} /><PageIntro eyebrow="Producto canónico" title={product.name} description={"Serie comparable " + basisLabel(product.basis) + " · " + product.summary.observationCount + " observaciones"}><span className="basis-pill">{basisLabel(product.basis)}</span></PageIntro><SummaryCards summary={product.summary} basis={product.basis} /><HistoryChart points={product.priceHistory} basis={product.basis} /><div className="subsection-heading"><div><p className="eyebrow">Trazabilidad</p><h2>Tickets relacionados</h2></div><span className="section-meta">{ticketsQuery.data ? ticketsQuery.data.totalItems + " apariciones" : ""}</span></div>{ticketsQuery.isPending ? <LoadingRows count={4} /> : ticketsQuery.isError ? <ErrorState error={ticketsQuery.error} retry={() => { void ticketsQuery.refetch(); }} /> : ticketsQuery.data.totalItems === 0 ? <EmptyState title="Sin tickets relacionados" text="Todavía no hay apariciones para este producto." /> : <><ProductTicketsTable data={ticketsQuery.data} /><Pagination page={ticketsQuery.data.page} totalPages={ticketsQuery.data.totalPages} onChange={(next) => setParams(next === 1 ? {} : { page: String(next) })} /></>}</section>;
}

function SyncPage() {
  const client = useQueryClient();
  const [runId, setRunId] = useState<string | null>(null);
  const statusQuery = useQuery({ queryKey: ["sync-status"], queryFn: ({ signal }) => api.getSyncStatus(signal), refetchInterval: 30000, retry: 1 });
  const runQuery = useQuery({ queryKey: ["sync-run", runId], queryFn: ({ signal }) => api.getSyncRun(runId || "", signal), enabled: Boolean(runId), refetchInterval: (query) => query.state.data?.status === "queued" || query.state.data?.status === "running" ? 1500 : false });
  const mutation = useMutation({ mutationFn: () => api.startSync(), onSuccess: (result) => { setRunId(result.id); void client.invalidateQueries({ queryKey: ["sync-status"] }); } });
  const status: SyncStatus | undefined = statusQuery.data;
  const run: SyncRun | undefined = runQuery.data;
  return <section className="page-content"><PageIntro eyebrow="Importación local" title="Sincronización" description="El equipo debe estar encendido para importar tickets y para acceder desde el móvil."><button className="button button-primary" type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending || status?.running}>{mutation.isPending ? "Iniciando…" : "Sincronizar ahora"}</button></PageIntro>{mutation.isError ? <div className="notice notice-danger" role="alert">{errorMessage(mutation.error)}</div> : null}{statusQuery.isPending ? <LoadingRows count={4} /> : statusQuery.isError ? <ErrorState error={statusQuery.error} retry={() => { void statusQuery.refetch(); }} /> : <div className="sync-grid"><div className="sync-card"><span className="eyebrow">Estado del host</span><strong>{status?.hostOnline ? "Disponible" : "Sin conexión"}</strong><p>La sincronización se ejecuta en este equipo.</p></div><div className="sync-card"><span className="eyebrow">Próxima ejecución</span><strong>{status?.nextScheduledAt ? formatDate(status.nextScheduledAt) : "No programada"}</strong><p>La tarea automática conserva el horario local.</p></div><div className="sync-card sync-card-wide"><span className="eyebrow">Última ejecución</span>{status?.lastRun ? <div className="run-summary"><StatusBadge status={status.lastRun.status} /><span>{formatDate(status.lastRun.finishedAt || status.lastRun.startedAt)}</span><span>{status.lastRun.importedTickets} tickets importados</span><span>{status.lastRun.errorCount} errores</span></div> : <p>Nunca se ha sincronizado.</p>}</div></div>}{run ? <div className="run-detail"><div className="subsection-heading"><div><p className="eyebrow">Ejecución actual</p><h2>{statusLabel(run.mode)}</h2></div><StatusBadge status={run.status} /></div><dl className="metric-list"><div><dt>Mensajes encontrados</dt><dd>{run.matchedMessages}</dd></div><div><dt>Tickets importados</dt><dd>{run.importedTickets}</dd></div><div><dt>Duplicados omitidos</dt><dd>{run.skippedDuplicates}</dd></div><div><dt>Tickets parciales</dt><dd>{run.partialTickets}</dd></div></dl>{run.errors.length ? <div className="notice notice-warning">{run.errors.map((item) => <div key={item.code}>{item.code}: {item.count}</div>)}</div> : null}</div> : null}</section>;
}

function Sidebar() {
  const { menuOpen, closeMenu } = useUiStore();
  return <aside className={menuOpen ? "sidebar sidebar-open" : "sidebar"} aria-label="Navegación principal"><div className="brand"><span className="brand-mark" aria-hidden="true">▦</span><span>Supermarket<br />Evolution</span></div><button className="sidebar-close" type="button" onClick={closeMenu}>Cerrar menú</button><nav aria-label="Navegación principal">{navItems.map((item) => <NavLink key={item.to} to={item.to} onClick={closeMenu} className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}><span>{item.label}</span><small>{item.hint}</small></NavLink>)}</nav><div className="sidebar-footer"><span className="dot" aria-hidden="true" />Fuente local · sin telemetría</div></aside>;
}
function Shell() {
  const { menuOpen, toggleMenu } = useUiStore();
  return <div className="app-shell"><button className="menu-button" type="button" onClick={toggleMenu} aria-expanded={menuOpen} aria-controls="main-navigation"><span aria-hidden="true">☰</span> Menú</button><Sidebar /><main id="main-navigation"><Routes><Route path="/" element={<Navigate to="/tickets" replace />} /><Route path="/tickets" element={<TicketsPage />} /><Route path="/tickets/:ticketId" element={<TicketDetailPage />} /><Route path="/products" element={<ProductsPage />} /><Route path="/products/:productId" element={<ProductDetailPage />} /><Route path="/sync" element={<SyncPage />} /><Route path="*" element={<section className="page-content"><EmptyState title="Página no encontrada" text="Volvé al registro de tickets para continuar." action={<Link className="button button-primary" to="/tickets">Ver tickets</Link>} /></section>} /></Routes></main></div>;
}
export default function App() { return <Shell />; }
