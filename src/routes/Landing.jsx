import { Button } from 'primereact/button';
import { Card } from 'primereact/card';
import { FileUpload } from 'primereact/fileupload';
import { Panel } from 'primereact/panel';
import { InputTextarea } from 'primereact/inputtextarea';
import { useState } from 'react';
import { useNavigate } from 'react-router';

const Landing = () => {
    const [text, setText] = useState('');
    const [slides, setSlides] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

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
            navigate('/dashboard', { state: { presentationUrl: data.presentationUrl, text: text } });
        } catch (err) {
            setError(err.message || 'Something went wrong while generating slides.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <div className="flex flex-column gap-4 justify-content-center align-items-center text-center" style={{ width: '50%' }}>
                <h1 className="m-0">Welcome to Upstart.ai!</h1>
                <div className="flex gap-4 w-full justify-content-center">
                    <InputTextarea className="blur" style={{ resize: 'none', width: '100%' }} placeholder="Tell us about your startup idea..." value={text} onChange={(e) => setText(e.target.value)} />
                    <Button icon={loading ? 'pi pi-spin pi-spinner' : 'pi pi-send'} className="p-button-primary" onClick={() => { handleCreateSlides() }} disabled={loading || !text.trim()} />
                </div>
                {error && <div style={{ color: '#f87171' }}>{error}</div>}

                {slides.length > 0 && (
                    <Panel header="Generated Slides" style={{ width: '50%', marginTop: '2rem' }}>
                        {slides.map((slide, index) => (
                            <Card key={index} title={slide.title} style={{ marginBottom: '1rem' }}>
                                <p>{slide.content}</p>
                            </Card>
                        ))}
                    </Panel>
                )}

                <Panel header="Upload some concept images/PDFs for context!" style={{ width: '100%' }}>
                    <FileUpload name="demo[]" url={'/api/upload'} multiple accept="image/*, application/pdf" maxFileSize={1000000} emptyTemplate={<p className="m-0">Drag and drop to upload.</p>} />
                </Panel>
            </div>
        </>
    );
}

export default Landing;