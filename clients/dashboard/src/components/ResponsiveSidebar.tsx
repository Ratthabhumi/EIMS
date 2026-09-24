"use client";

import * as React from "react";
import { Menu, X } from "lucide-react";
import { SidebarNav } from "@/components/SidebarNav";
import { usePathname } from "next/navigation";

export function ResponsiveSidebar() {
  const [isOpen, setIsOpen] = React.useState(false);
  const pathname = usePathname();

  const closeSidebar = () => setIsOpen(false);

  React.useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setIsOpen(false);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <>
      {/* Mobile/Tablet: Overlay — only rendered when open; isOpen starts false
          deterministically on both server and client. */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      {/* Sidebar — className is deterministic (depends only on isOpen).
          Responsive width/toggling is driven by Tailwind `lg:` utilities. */}
      <aside
        id="sidebar"
        className={`
          fixed lg:relative z-50 h-screen lg:h-auto bg-eims-surface border-r border-eims-border
          flex flex-col transition-all duration-200 shrink-0
          w-72 lg:w-64
          ${isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
        aria-label="Main navigation"
      >
        <div className="h-16 flex items-center px-6 border-b border-eims-border">
          <div className="font-bold text-lg tracking-tight text-eims-text flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-sm bg-eims-accent" />
            EIMS Portal
          </div>
        </div>

        <SidebarNav onNavigate={closeSidebar} />
      </aside>

      {/* Hamburger button — always present in the DOM on both server and
          client; CSS (`lg:hidden`) controls visibility below the lg breakpoint. */}
      <button
        className="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-lg bg-eims-surface border border-eims-border text-eims-text hover:bg-eims-surface-subtle transition-colors"
        onClick={() => setIsOpen(true)}
        aria-label="Open navigation menu"
        aria-expanded={isOpen}
        aria-controls="sidebar"
      >
        <Menu className="w-5 h-5" />
      </button>
    </>
  );
}
