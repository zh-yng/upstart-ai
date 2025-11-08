import { useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { Button } from 'primereact/button';
import { Panel } from 'primereact/panel';

const extractPresentationId = (url) => {
    if (typeof url !== 'string') {
        return null;
    }
    const match = url.match(/presentation\/d\/([^/]+)/i);
    return match ? match[1] : null;
};

const Download = ({ presentationUrl }) => {
    const navigate = useNavigate();

    useEffect(() => {
        if (!presentationUrl) {
            navigate('/', { replace: true });
        }
    }, [presentationUrl, navigate]);

    const downloadUrl = useMemo(() => {
        const presentationId = extractPresentationId(presentationUrl);
        return presentationId
            ? `https://docs.google.com/presentation/d/${presentationId}/export/pptx`
            : presentationUrl;
    }, [presentationUrl]);

    if (!presentationUrl) {
        return null;
    }

    const handleDownload = () => {
        window.open(downloadUrl, '_blank', 'noopener,noreferrer');
    };

    const handleViewOnline = () => {
        window.open(presentationUrl, '_blank', 'noopener,noreferrer');
    };

    return (
        <div className="flex flex-column gap-4 align-items-center text-center" style={{ width: '100%' }}>
            <h2 className="m-0">Your presentation is ready!</h2>
            <Panel header="Download Options" style={{ width: '100%' }}>
                <p style={{ marginBottom: '1.5rem' }}>
                    Click below to download the deck as a PowerPoint file, or view it directly in Google Slides.
                </p>
                <div className="flex gap-3 justify-content-center flex-wrap">
                    <Button label="Download PPTX" icon="pi pi-download" onClick={handleDownload} className="p-button-success" />
                    <Button label="Open in Google Slides" icon="pi pi-external-link" onClick={handleViewOnline} outlined />
                </div>
            </Panel>
            <Button label="Back to Home" icon="pi pi-home" onClick={() => navigate('/')} link />
        </div>
    );
};

export default Download;
