import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Store, Calendar, Users, CheckCircle } from 'lucide-react';

export default function TestUI() {
    return (
        <div className="p-8 space-y-8 bg-muted/20 min-h-screen">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-foreground">UI Design System</h1>
                <p className="text-muted-foreground">Professional Sapphire Theme - Component Verification</p>
            </div>

            {/* Buttons Section */}
            <section className="space-y-4">
                <h2 className="text-xl font-semibold">Buttons</h2>
                <div className="flex flex-wrap gap-4 p-6 border rounded-lg bg-card/50 backdrop-blur-sm">
                    <Button variant="primary">Primary Action</Button>
                    <Button variant="secondary">Secondary Action</Button>
                    <Button variant="outline">Outline</Button>
                    <Button variant="ghost">Ghost Button</Button>
                    <Button variant="danger">Danger Zone</Button>
                    <Button variant="primary" isLoading>Loading</Button>
                    <Button variant="primary" disabled>Disabled</Button>
                </div>
            </section>

            {/* Cards Section */}
            <section className="space-y-4">
                <h2 className="text-xl font-semibold">Cards & Containers</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Standard Card */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Store className="w-5 h-5 text-primary" />
                                Standard Card
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-muted-foreground">
                                This is a standard card with the new glassmorphism effect on the background and subtle borders.
                            </p>
                            <div className="mt-4 flex justify-end">
                                <Button size="sm">Action</Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Stats Card */}
                    <Card className="border-l-4 border-l-primary">
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-muted-foreground">Total Appointments</p>
                                    <h3 className="text-2xl font-bold mt-1">1,248</h3>
                                </div>
                                <div className="p-3 bg-primary/10 rounded-full">
                                    <Calendar className="w-6 h-6 text-primary" />
                                </div>
                            </div>
                            <div className="mt-4 flex items-center text-sm text-success">
                                <CheckCircle className="w-4 h-4 mr-1" />
                                <span className="font-medium">+12%</span>
                                <span className="text-muted-foreground ml-1">last month</span>
                            </div>
                        </CardContent>
                    </Card>

                    {/* User Card */}
                    <Card>
                        <CardContent className="pt-6 text-center">
                            <div className="w-16 h-16 bg-gradient-to-br from-primary to-secondary rounded-full mx-auto flex items-center justify-center text-white text-xl font-bold mb-3 shadow-lg">
                                JD
                            </div>
                            <h3 className="font-semibold text-lg">John Doe</h3>
                            <p className="text-sm text-muted-foreground mb-4">Professional Barber</p>
                            <div className="flex justify-center gap-2">
                                <Badge variant="default">Active</Badge>
                                <Badge variant="secondary">Pro</Badge>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </section>

            {/* Form Elements */}
            <section className="space-y-4">
                <h2 className="text-xl font-semibold">Form Elements</h2>
                <Card className="max-w-md">
                    <CardContent className="space-y-4 pt-6">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Email Address</label>
                            <Input placeholder="name@example.com" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Full Name</label>
                            <Input placeholder="John Doe" />
                        </div>
                        <Button className="w-full">Submit Form</Button>
                    </CardContent>
                </Card>
            </section>
        </div>
    );
}
