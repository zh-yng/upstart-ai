import { Button } from 'primereact/button';
import { Card } from 'primereact/card';
import { InputText } from 'primereact/inputtext';
import { FileUpload } from 'primereact/fileupload';
import { Panel } from 'primereact/panel';
import { InputTextarea } from 'primereact/inputtextarea';

const Landing = () => {

    return (
        <>
            <div className="flex flex-column gap-4 justify-content-center align-items-center text-center" style={{ width: '50%' }}>
                <h1 className="m-0">Welcome to Upstart.ai!</h1>
                <div className="flex gap-4 w-full justify-content-center">
                    <InputTextarea className="blur" style={{ resize: 'none', width: '100%' }} placeholder="Tell us about your startup idea..." />
                    <Button icon="pi pi-send" className="p-button-primary" />
                </div>
                <Panel header="Upload your plan docs" style={{ width: '100%' }}>
                    <FileUpload name="demo[]" url={'/api/upload'} multiple accept="application/pdf" maxFileSize={1000000} emptyTemplate={<p className="m-0">Drag and drop PDFs to upload.</p>} />
                </Panel>
            </div >
        </>
    );
}

export default Landing;