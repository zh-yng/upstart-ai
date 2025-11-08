import { Button } from "primereact/button";
import { Ripple } from 'primereact/ripple';
import { useLocation } from "react-router";
import { Card } from "primereact/card";
import { useState } from "react";
import { Dialog } from "primereact/dialog";

const Dashboard = () => {
    const location = useLocation();
    const presentationUrl = location.state && location.state.presentationUrl;
    const text = location.state?.text || '';
    
    const [roadmapLoading, setRoadmapLoading] = useState(false);
    const [roadmapReady, setRoadmapReady] = useState(false);
    const [showRoadmapDialog, setShowRoadmapDialog] = useState(false);

    const features = [
        { name: 'Slides', icon: 'pi pi-id-card', route: '/api/create_slides', content: (presentationUrl != null) ? presentationUrl : '', color: 'rgba(248, 191, 8,1)' },
        { name: 'Video', icon: 'pi pi-video', route: '/api/video', content: '', color: 'rgba(8, 191, 248, 1)' },
        { name: 'Network', icon: 'pi pi-sitemap', route: '/api/network', content: '', color: 'rgba(191, 8, 248,1)' },
        { name: 'Roadmap', icon: 'pi pi-map', route: '/api/create_roadmap', content: '', color: 'rgba(248, 191, 8,1)', loadingColor: 'rgba(191, 8, 248,1)', handler: 'roadmap' },
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
            alert('Please enter a prompt before generating slides.');
            return;
        }

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

            window.location.href = data.presentationUrl;
        } catch (err) {
            alert(err.message || 'Something went wrong while generating slides.');
        }
    };

    const handleCreateRoadmap = async () => {
        if (!text.trim()) {
            alert('Please enter a prompt before generating roadmap.');
            return;
        }

        setRoadmapLoading(true);
        setRoadmapReady(false);

        try {
            const response = await fetch(`/api/create_roadmap`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text.trim(), download: false }),
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to generate roadmap.');
            }

            setRoadmapReady(true);
            setShowRoadmapDialog(true);
        } catch (err) {
            alert(err.message || 'Something went wrong while generating roadmap.');
        } finally {
            setRoadmapLoading(false);
        }
    };

    const handleViewRoadmap = async () => {
        try {
            const response = await fetch(`/api/create_roadmap`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text.trim(), download: false }),
            });

            if (!response.ok) {
                throw new Error('Failed to retrieve roadmap.');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            window.open(url, '_blank');
            setShowRoadmapDialog(false);
        } catch (err) {
            alert(err.message || 'Something went wrong while viewing roadmap.');
        }
    };

    const handleDownloadRoadmap = async () => {
        try {
            const response = await fetch(`/api/create_roadmap`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text.trim(), download: true }),
            });

            if (!response.ok) {
                throw new Error('Failed to download roadmap.');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'startup_roadmap.pdf';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            setShowRoadmapDialog(false);
        } catch (err) {
            alert(err.message || 'Something went wrong while downloading roadmap.');
        }
    };

    return (
        <>
            <div className="flex flex-column gap-2 justify-content-center align-items-center text-center" style={{ width: '50%' }}>
                <div className="flex flex-column gap-2 w-full justify-content-center">
                    {/* two per row grid of buttons */}
                    <div className="flex gap-2 w-full">
                        <div className="flex flex-column gap-2 justify-content-center" style={{ width: '30vw' }}>
                            {features.map((feature) => {
                                const isRoadmap = feature.handler === 'roadmap';
                                const isLoading = isRoadmap && roadmapLoading;
                                const isReady = isRoadmap && roadmapReady;
                                const buttonColor = isLoading ? (feature.loadingColor || feature.color) : (isReady ? feature.color : 'rgba(255, 255, 255,1)');
                                const cardBgColor = (feature.content !== '' || isReady) ? feature.color : 'transparent';

                                return (
                                <Card title={feature.name} key={feature.name} className="blur flex flex-column justify-content-center align-items-center" style={{ backgroundColor: cardBgColor }}>
                                    {(feature.content === "" && !isReady) ?

                                        <Button
                                            key={feature.name}
                                            className="blur justify-content-start"
                                            style={{ border: '1px dashed black', color: 'black', backgroundColor: buttonColor, minHeight: '50px' }}
                                            icon={isLoading ? 'pi pi-spin pi-spinner' : feature.icon}
                                            label={isLoading ? "Generating..." : "Generate"}
                                            severity="secondary"
                                            disabled={isLoading}
                                            onClick={() => {
                                                if (feature.handler === 'roadmap') {
                                                    handleCreateRoadmap();
                                                } else {
                                                    window.location.href = feature.content;
                                                }
                                            }}
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
                                                onClick={() => {
                                                    if (isRoadmap) {
                                                        handleCreateRoadmap();
                                                    } else {
                                                        handleCreateSlides();
                                                    }
                                                }}
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
                                                icon={isRoadmap ? 'pi pi-file-pdf' : 'pi pi-external-link'}
                                                severity="primary"
                                                onClick={() => {
                                                    if (isRoadmap) {
                                                        setShowRoadmapDialog(true);
                                                    } else {
                                                        window.location.href = feature.content;
                                                    }
                                                }}
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
                                );
                            })}
                        </div>
                        <div style={{ width: '50vw' }} className="blur border flex flex-column justify-content-center align-items-center">
                            <h3>Chat with Everest</h3>
                        </div>
                    </div>
                </div >
            </div >
            
            <Dialog 
                header="Roadmap Ready" 
                visible={showRoadmapDialog} 
                onHide={() => setShowRoadmapDialog(false)}
                style={{ width: '450px' }}
                modal
            >
                <div className="flex flex-column gap-3 align-items-center">
                    <p className="m-0">Your startup roadmap is ready! How would you like to access it?</p>
                    <div className="flex gap-2 w-full">
                        <Button 
                            label="View in Browser" 
                            icon="pi pi-eye" 
                            className="flex-1"
                            onClick={handleViewRoadmap}
                        />
                        <Button 
                            label="Download PDF" 
                            icon="pi pi-download" 
                            className="flex-1"
                            severity="success"
                            onClick={handleDownloadRoadmap}
                        />
                    </div>
                </div>
            </Dialog>
        </>
    );
}

export default Dashboard;