import { Button } from "primereact/button";
import { Ripple } from 'primereact/ripple';
import { useLocation } from "react-router";
import { Card } from "primereact/card";
import { useState } from "react";
import { Dialog } from "primereact/dialog";
import { InputTextarea } from "primereact/inputtextarea";

const Dashboard = () => {
    const location = useLocation();
    const presentationUrl = location.state && location.state.presentationUrl;
    const text = location.state?.text || '';

    const [roadmapLoading, setRoadmapLoading] = useState(false);
    const [roadmapReady, setRoadmapReady] = useState(false);
    const [showRoadmapDialog, setShowRoadmapDialog] = useState(false);

    const [videoLoading, setVideoLoading] = useState(false);
    const [videoReady, setVideoReady] = useState(false);
    const [showVideoDialog, setShowVideoDialog] = useState(false);

    const [chatMessages, setChatMessages] = useState([
        { role: 'assistant', text: 'Hello! I\'m Everest, your AI startup assistant. How can I help you today?' }
    ]);
    const [chatInput, setChatInput] = useState('');

    const features = [
        { name: 'Slides', icon: 'pi pi-id-card', route: '/api/create_slides', content: (presentationUrl != null) ? presentationUrl : '', color: 'rgba(248, 191, 8,1)', handler: 'slides' },
        { name: 'Video', icon: 'pi pi-video', route: '/api/create_video', content: '', color: 'rgba(8, 191, 248, 1)', loadingColor: 'rgba(191, 8, 248,1)', handler: 'video' },
        { name: 'Network', icon: 'pi pi-sitemap', route: '/api/network', content: '', color: 'rgba(191, 8, 248,1)', handler: 'network' },
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

            window.open(data.presentationUrl, '_blank');
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

    const handleCreateVideo = async () => {
        if (!text.trim()) {
            alert('Please enter a prompt before generating video.');
            return;
        }

        setVideoLoading(true);
        setVideoReady(false);

        try {
            const response = await fetch(`/api/create_video`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text.trim(), download: false }),
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to generate video.');
            }

            setVideoReady(true);
            setShowVideoDialog(true);
        } catch (err) {
            alert(err.message || 'Something went wrong while generating video.');
        } finally {
            setVideoLoading(false);
        }
    };

    const handleChatSubmit = async () => {
        if (!chatInput.trim()) return;

        // Add user message
        const userMessage = { role: 'user', text: chatInput };
        setChatMessages(prev => [...prev, userMessage]);

        // Store input before clearing
        const currentInput = chatInput;

        // Clear input
        setChatInput('');

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: currentInput,
                    businessIdea: text.trim(),
                    chatHistory: chatMessages
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to process chat message');
            }

            // Add bot response
            const botResponse = {
                role: 'assistant',
                text: data.response || 'Sorry, I couldn\'t process that request.'
            };
            setChatMessages(prev => [...prev, botResponse]);

        } catch (err) {
            console.error('Chat error:', err);
            const errorResponse = {
                role: 'assistant',
                text: 'Sorry, something went wrong. Please try again.'
            };
            setChatMessages(prev => [...prev, errorResponse]);
        }
    };

    const handleViewVideo = async () => {
        try {
            const response = await fetch(`/api/create_video`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text.trim(), download: false }),
            });

            if (!response.ok) {
                throw new Error('Failed to retrieve video.');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            window.open(url, '_blank');
            setShowVideoDialog(false);
        } catch (err) {
            alert(err.message || 'Something went wrong while viewing video.');
        }
    };

    const handleDownloadVideo = async () => {
        try {
            const response = await fetch(`/api/create_video`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text.trim(), download: true }),
            });

            if (!response.ok) {
                throw new Error('Failed to download video.');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'startup_ad_video.mp4';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            setShowVideoDialog(false);
        } catch (err) {
            alert(err.message || 'Something went wrong while downloading video.');
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

    return (
        <>
            <div className="flex flex-column gap-2 justify-content-center align-items-center text-center" style={{ width: '50%' }}>
                <div className="flex flex-column gap-2 w-full justify-content-center">
                    {/* two per row grid of buttons */}
                    <div className="flex gap-2 w-full align-items-center">
                        <div className="flex flex-column gap-2 justify-content-center" style={{ width: '30vw' }}>
                            {features.map((feature) => {
                                const isRoadmap = feature.handler === 'roadmap';
                                const isVideo = feature.handler === 'video';
                                const isNetwork = feature.handler === 'network';
                                const isSlides = feature.handler === 'slides';
                                const isLoading = (isRoadmap && roadmapLoading) || (isVideo && videoLoading);
                                const isReady = (isRoadmap && roadmapReady) || (isVideo && videoReady);
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
                                                    } else if (feature.handler === 'video') {
                                                        handleCreateVideo();
                                                    } else if (feature.handler === 'network') {
                                                        handleCreateNetwork();
                                                    } else if (feature.handler === 'slides') {
                                                        handleCreateSlides();
                                                    } else {
                                                        window.open(feature.content, '_blank');
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
                                                        } else if (isVideo) {
                                                            handleCreateVideo();
                                                        } else if (isNetwork) {
                                                            handleCreateNetwork();
                                                        } else if (isSlides) {
                                                            handleCreateSlides();
                                                        } else {
                                                            window.open(feature.content, '_blank');
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
                                                    icon={(isRoadmap || isVideo) ? 'pi pi-file' : 'pi pi-external-link'}
                                                    severity="primary"
                                                    onClick={() => {
                                                        if (isRoadmap) {
                                                            setShowRoadmapDialog(true);
                                                        } else if (isVideo) {
                                                            setShowVideoDialog(true);
                                                        } else if (isNetwork) {
                                                            handleCreateNetwork();
                                                        } else {
                                                            window.open(feature.content, '_blank');
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
                        <div style={{ width: '50vw', height: '70vh', borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }} className="blur border">
                            {/* Chat Header */}
                            <div style={{
                                padding: '1rem 1.5rem',
                                borderBottom: '1px solid rgba(255,255,255,0.2)',
                                background: 'rgba(191, 8, 248, 0.1)',
                                flexShrink: 0
                            }}>
                                <h3 className="m-0 flex align-items-center gap-2">
                                    <i className="pi pi-comments" style={{ fontSize: '1.5rem' }}></i>
                                    Chat with Everest
                                </h3>
                                <p className="m-0 mt-1" style={{ fontSize: '0.875rem', opacity: 0.8 }}>
                                    Your AI startup assistant
                                </p>
                            </div>

                            {/* Chat Messages */}
                            <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', minHeight: 0 }}>
                                <div className="flex flex-column gap-3">
                                    {chatMessages.map((msg, index) => (
                                        <div
                                            key={index}
                                            className={`flex ${msg.role === 'user' ? 'justify-content-end' : 'justify-content-start'}`}
                                        >
                                            <div
                                                style={{
                                                    maxWidth: '75%',
                                                    padding: '0.75rem 1rem',
                                                    borderRadius: '12px',
                                                    background: msg.role === 'user'
                                                        ? 'rgba(8, 191, 248, 0.2)'
                                                        : 'rgba(191, 8, 248, 0.2)',
                                                    border: `1px solid ${msg.role === 'user'
                                                        ? 'rgba(8, 191, 248, 0.4)'
                                                        : 'rgba(191, 8, 248, 0.4)'}`,
                                                }}
                                            >
                                                {msg.role === 'assistant' && (
                                                    <div className="flex align-items-center gap-2 mb-2">
                                                        <i className="pi pi-sparkles" style={{ fontSize: '0.875rem' }}></i>
                                                        <strong style={{ fontSize: '0.875rem' }}>Everest</strong>
                                                    </div>
                                                )}
                                                <p className="m-0" style={{ fontSize: '0.95rem', lineHeight: '1.5' }}>
                                                    {msg.text}
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Chat Input */}
                            <div style={{
                                padding: '1rem',
                                borderTop: '1px solid rgba(255,255,255,0.2)',
                                background: 'rgba(0, 0, 0, 0.1)',
                                flexShrink: 0
                            }}>
                                <div className="flex gap-2">
                                    <InputTextarea
                                        value={chatInput}
                                        onChange={(e) => setChatInput(e.target.value)}
                                        placeholder="Type your message here..."
                                        rows={2}
                                        autoResize
                                        style={{ flex: 1 }}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                e.preventDefault();
                                                handleChatSubmit();
                                            }
                                        }}
                                    />
                                    <Button
                                        icon="pi pi-send"
                                        onClick={handleChatSubmit}
                                        style={{
                                            background: 'rgba(191, 8, 248, 0.8)',
                                            border: '1px solid rgba(191, 8, 248, 1)',
                                            height: 'fit-content',
                                            alignSelf: 'flex-end'
                                        }}
                                        tooltip="Send message"
                                        tooltipOptions={{ position: 'top' }}
                                    />
                                </div>
                            </div>
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

            <Dialog
                header="Video Ready"
                visible={showVideoDialog}
                onHide={() => setShowVideoDialog(false)}
                style={{ width: '450px' }}
                modal
            >
                <div className="flex flex-column gap-3 align-items-center">
                    <p className="m-0">Your startup advertisement video is ready! How would you like to access it?</p>
                    <div className="flex gap-2 w-full">
                        <Button
                            label="View in Browser"
                            icon="pi pi-eye"
                            className="flex-1"
                            onClick={handleViewVideo}
                        />
                        <Button
                            label="Download MP4"
                            icon="pi pi-download"
                            className="flex-1"
                            severity="success"
                            onClick={handleDownloadVideo}
                        />
                    </div>
                </div>
            </Dialog>
        </>
    );
}

export default Dashboard;