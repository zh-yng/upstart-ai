import { Button } from "primereact/button";
import { Ripple } from 'primereact/ripple';

const Dashboard = () => {
    const features = [
        { name: 'Slides', icon: 'pi pi-id-card', route: '/api/slides' },
        { name: 'Video', icon: 'pi pi-video', route: '/api/video' },
        { name: 'Network', icon: 'pi pi-sitemap', route: '/api/network' },
        { name: 'Code', icon: 'pi pi-code', route: '/api/code' },
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

    return (
        <>
            <Button onClick={handleGetHello} label="Test API Connection" className="mb-4" />
            <div className="flex flex-column gap-4 justify-content-center align-items-center text-center" style={{ width: '50%' }}>
                <div className="flex flex-column gap-4 w-full justify-content-center">
                    {/* two per row grid of buttons */}
                    <div className="flex gap-4 w-full">
                        <div className="flex flex-column gap-4 w-full justify-content-center">
                            {features.map((feature) => (
                                <Button
                                    key={feature.name}
                                    className="blur justify-content-start border"
                                    style={{ color: 'black', maxWidth: '300px', width: '100%', minHeight: '100px' }}
                                    icon={feature.icon}
                                    label={feature.name}
                                    severity="secondary"
                                    onClick={() => window.location.href = feature.route}
                                >
                                    <Ripple
                                        pt={{
                                            root: { style: { background: 'rgba(0, 0, 0, 0.3)' } }
                                        }}
                                    />
                                </Button>
                            ))}
                        </div>
                        <div style={{ minWidth: '30vw' }} className="blur border flex flex-column justify-content-center align-items-center">
                            <h3>Chat with Everest</h3>
                        </div>
                    </div>
                </div >
            </div >
        </>
    );
}

export default Dashboard;