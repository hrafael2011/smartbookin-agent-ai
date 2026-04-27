import { Component, ErrorInfo, ReactNode } from 'react';
import { TriangleAlert, RotateCcw } from 'lucide-react';
import { Button } from './Button';

interface Props {
    children?: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false
    };

    public static getDerivedStateFromError(_: Error): State {
        return { hasError: true };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return this.props.fallback || (
                <div className="min-h-screen flex items-center justify-center bg-background p-6">
                    <div className="max-w-md w-full bg-card rounded-xl shadow-lg border border-border p-8 text-center space-y-6">
                        <div className="mx-auto w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center">
                            <TriangleAlert className="h-8 w-8 text-destructive" />
                        </div>

                        <div className="space-y-2">
                            <h1 className="text-2xl font-bold text-foreground">¡Uy! Algo salió mal</h1>
                            <p className="text-muted-foreground">
                                Ha ocurrido un error inesperado. Hemos registrado el problema e intentaremos solucionarlo lo antes posible.
                            </p>
                        </div>

                        <div className="pt-4">
                            <Button
                                onClick={() => window.location.reload()}
                                className="w-full"
                            >
                                <RotateCcw className="mr-2 h-4 w-4" />
                                Recargar Página
                            </Button>
                        </div>

                        <p className="text-xs text-muted-foreground">
                            Si el problema persiste, por favor contacte con soporte técnico.
                        </p>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
