import { FileQuestion, Home } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui';

export function NotFound() {
    return (
        <div className="min-h-screen flex items-center justify-center bg-background p-6">
            <div className="max-w-md w-full text-center space-y-8 animate-in fade-in zoom-in duration-500">
                <div className="relative mx-auto w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center">
                    <FileQuestion className="h-12 w-12 text-primary" />
                    <div className="absolute -top-1 -right-1 w-6 h-6 bg-background border-2 border-primary text-primary text-[10px] font-bold rounded-full flex items-center justify-center">
                        404
                    </div>
                </div>

                <div className="space-y-3">
                    <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl">
                        Página No Encontrada
                    </h1>
                    <p className="text-lg text-muted-foreground">
                        Lo sentimos, no pudimos encontrar la página que estás buscando. Es posible que haya sido movida o eliminada.
                    </p>
                </div>

                <div className="pt-4">
                    <Link to="/">
                        <Button size="lg" className="w-full sm:w-auto shadow-lg shadow-primary/20">
                            <Home className="mr-2 h-5 w-5" />
                            Volver al Inicio
                        </Button>
                    </Link>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-8">
                    <div className="p-4 bg-muted/40 rounded-lg border border-border/60 text-left">
                        <h3 className="text-sm font-semibold text-foreground mb-1">¿Algún problema?</h3>
                        <p className="text-xs text-muted-foreground">Revisa la URL o intenta navegar desde el menú.</p>
                    </div>
                    <div className="p-4 bg-muted/40 rounded-lg border border-border/60 text-left">
                        <h3 className="text-sm font-semibold text-foreground mb-1">Soporte</h3>
                        <p className="text-xs text-muted-foreground">Contáctanos si crees que esto es un error.</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
