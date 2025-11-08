import { Button } from "primereact/button";
import { Ripple } from 'primereact/ripple';
import { useLocation } from "react-router";
import { Card } from "primereact/card";

const Dashboard = () => {
    const location = useLocation();
    const presentationUrl = location.state && location.state.presentationUrl;
    const text = location.state || location.state.text;

    const features = [
        { name: 'Slides', icon: 'pi pi-id-card', route: '/api/create_slides', content: (presentationUrl != null) ? presentationUrl : '', color: 'rgba(248, 191, 8,1)' },
        { name: 'Video', icon: 'pi pi-video', route: '/api/video', content: '', color: 'rgba(8, 191, 248, 1)' },
        { name: 'Network', icon: 'pi pi-sitemap', route: '/api/network', content: '', color: 'rgba(191, 8, 248,1)' },
        { name: 'Code', icon: 'pi pi-code', route: '/api/code', content: '', color: 'rgba(0, 190, 140,1)' },
    ]

    const handleGetHello = async () => {
        try {
            const response = await fetch('/api/hello');
            const data = await response.json();
            console.log('GET /api/hello response:', data);
        } catch (error) {
            console.error('Error fetching /api/hello:', error);
        }
    }

    const handleCreateSlides = async () => {
        if (!text.trim()) {
            setError('Please enter a prompt before generating slides.');
            return;
        }

        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`/api/create_slides`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text.trim() }),
            });

            let data = {};
            try {
                data = await response.json();
            } catch (parseErr) {
                if (!response.ok) {
                    throw new Error('Failed to generate slides.');
                }
                throw parseErr;
            }

            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate slides.');
            }
            if (!data.presentationUrl) {
                throw new Error('Presentation link not found in response.');
            }

            navigate('/dashboard', { state: { presentationUrl: data.presentationUrl } });
        } catch (err) {
            setError(err.message || 'Something went wrong while generating slides.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <div className="flex flex-column gap-2 justify-content-center align-items-center text-center" style={{ width: '50%' }}>
                <div className="flex flex-column gap-2 w-full justify-content-center">
                    {/* two per row grid of buttons */}
                    <div className="flex gap-2 w-full">
                        <div className="flex flex-column gap-2 justify-content-center" style={{ width: '30vw' }}>
                            {features.map((feature) => (
                                <Card title={feature.name} key={feature.name} className="blur flex flex-column justify-content-center align-items-center" style={{ backgroundColor: (feature.content === '') ? 'transparent' : feature.color }}>
                                    {feature.content === "" ?

                                        <Button
                                            key={feature.name}
                                            className="blur justify-content-start"
                                            style={{ border: '1px dashed black', color: 'black', backgroundColor: 'rgba(255, 255, 255,1)', minHeight: '50px' }}
                                            icon={feature.icon}
                                            label={"Generate"}
                                            severity="secondary"
                                            onClick={() => window.location.href = feature.content}
                                        >
                                            <Ripple
                                                pt={{
                                                    root: { style: { background: feature.color } }
                                                }}
                                            />
                                        </Button>

                                        :

                                        <span className="flex gap-2 w-full justify-content-center align-items-center">
                                            <Button
                                                key={feature.name}
                                                className="blur justify-content-start"
                                                style={{ border: '1px dashed black', color: 'black', backgroundColor: feature.color, minHeight: '50px' }}
                                                icon={'pi pi-refresh'}
                                                label={"Redo?"}
                                                severity="secondary"
                                                onClick={() => handleCreateSlides()}
                                            >
                                                <Ripple
                                                    pt={{
                                                        root: { style: { background: feature.color } }
                                                    }}
                                                />
                                            </Button>
                                            <Button
                                                key={feature.name}
                                                className="blur justify-content-start"
                                                style={{ border: '1px solid black', backgroundColor: 'rgba(255, 255, 255,1)', color: 'black', minHeight: '50px' }}
                                                icon={'pi pi-external-link'}
                                                severity="primary"
                                                onClick={() => window.location.href = feature.content}
                                            >
                                                <Ripple
                                                    pt={{
                                                        root: { style: { background: feature.color } }
                                                    }}
                                                />
                                            </Button>
                                        </span>
                                    }

                                </Card>
                            ))}
                        </div>
                        <div style={{ width: '50vw' }} className="blur border flex flex-column justify-content-center align-items-center">
                            <h3>Chat with Everest</h3>
                        </div>
                    </div>
                </div >
            </div >
        </>
    );
}

export default Dashboard;