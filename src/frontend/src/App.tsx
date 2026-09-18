import { NavLink, Route, Routes } from "react-router-dom";
import { useUiStore } from "./state/uiStore";

const links = [
  { to: "/tickets", label: "Tickets" },
  { to: "/products", label: "Productos" },
  { to: "/sync", label: "Sincronización" }
];

function Page({ title, text }: { title: string; text: string }) {
  return <section className="page"><p className="eyebrow">Mercadona Evolution</p><h1>{title}</h1><p className="muted">{text}</p></section>;
}

function Shell() {
  const { menuOpen, toggleMenu, closeMenu } = useUiStore();
  return (
    <div className="app-shell">
      <button className="menu-button" type="button" onClick={toggleMenu} aria-expanded={menuOpen} aria-controls="main-navigation">
        <span aria-hidden="true">☰</span> Menú
      </button>
      <aside id="main-navigation" className={menuOpen ? "sidebar sidebar-open" : "sidebar"} aria-label="Navegación principal">
        <div className="brand"><span className="brand-mark" aria-hidden="true">◆</span><span>Supermarket Evolution</span></div>
        <nav aria-label="Navegación principal">
          {links.map((link) => <NavLink key={link.to} to={link.to} onClick={closeMenu} className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>{link.label}</NavLink>)}
        </nav>
      </aside>
      <main><Routes>
        <Route path="/" element={<Page title="Tu evolución de precios" text="Selecciona una sección para comenzar." />} />
        <Route path="/tickets" element={<Page title="Tickets" text="Aquí aparecerán tus tickets sincronizados." />} />
        <Route path="/tickets/:ticketId" element={<Page title="Detalle del ticket" text="El detalle del ticket estará disponible en la siguiente fase." />} />
        <Route path="/products" element={<Page title="Productos" text="Busca productos para consultar su evolución." />} />
        <Route path="/products/:productId" element={<Page title="Evolución del producto" text="La evolución histórica se mostrará aquí." />} />
        <Route path="/sync" element={<Page title="Sincronización" text="Todavía no hay ejecuciones de sincronización." />} />
      </Routes></main>
    </div>
  );
}

export default function App() { return <Shell />; }
