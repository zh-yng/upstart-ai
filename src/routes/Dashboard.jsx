import { Button } from "primereact/button";
import { Ripple } from 'primereact/ripple';
import { useLocation } from "react-router";
import { Card } from "primereact/card";
import { useState } from "react";

const Dashboard = () => {
    const location = useLocation();
    const presentationUrl = location.state && location.state.presentationUrl;
    const text = location.state && location.state.text;
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

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
        if (!text) {
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
                body: JSON.stringify({ text: text }),
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

    const handleCreateNetwork = async () => {
        console.log(text);
        try {
            const response = await fetch('/api/find-investors', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ idea: text }),
            });
            const data = await response.json();
            console.log('Network generation response:', data);
        } catch (error) {
            console.error('Error generating network:', error);
        }
    };

    const features = [
        { name: 'Slides', icon: 'pi pi-id-card', route: '/api/create_slides', content: (presentationUrl != null) ? presentationUrl : '', color: 'rgba(248, 191, 8,1)', onClick: handleCreateSlides },
        { name: 'Video', icon: 'pi pi-video', route: '/api/video', content: '', color: 'rgba(8, 191, 248, 1)' },
        { name: 'Network', icon: 'pi pi-sitemap', route: '/api/create_network', content: '', color: 'rgba(191, 8, 248,1)', onClick: handleCreateNetwork },
        { name: 'Website', icon: 'pi pi-code', route: '/api/code', content: '', color: 'rgba(0, 190, 140,1)' },
    ]

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

                                        (feature.onClick && <Button
                                            key={feature.name}
                                            className="blur justify-content-start"
                                            style={{ border: '1px dashed black', color: 'black', backgroundColor: 'rgba(255, 255, 255,1)', minHeight: '50px' }}
                                            icon={loading ? feature.icon : 'pi-refresh'}
                                            label={loading ? "Loading..." : "Generate"}
                                            severity="secondary"
                                            onClick={() => feature.onClick()}
                                        >
                                            <Ripple
                                                pt={{
                                                    root: { style: { background: feature.color } }
                                                }}
                                            />
                                        </Button>)

                                        :

                                        <span className="flex gap-2 w-full justify-content-center align-items-center">
                                            {feature.onClick && <Button
                                                key={feature.name}
                                                className="blur justify-content-start"
                                                style={{ border: '1px dashed black', color: 'black', backgroundColor: feature.color, minHeight: '50px' }}
                                                icon={'pi pi-refresh'}
                                                label={"Redo?"}
                                                severity="secondary"
                                                // change the onclick to call the feature's onClick function
                                                onClick={feature.onClick}
                                            >
                                                <Ripple
                                                    pt={{
                                                        root: { style: { background: feature.color } }
                                                    }}
                                                />
                                            </Button>}
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