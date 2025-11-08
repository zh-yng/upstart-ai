import express from "express";
import ViteExpress from "vite-express";
import spawn from 'child_process';

const app = express();
app.use(express.json());

app.get("/api/hello", (req, res) => {
    res.json({ message: "Hello from ViteExpress server!" });
});

// implement slide-generation endpoint from app.py
app.post("/api/create_slides", (req, res) => {
    const { text } = req.body;
    const pyProg = spawn('python', ['backend/api/slide_create.py']);

    pyProg.stdout.on('data', function (data) {

        console.log(data.toString());
        res.write(data);
        res.end('end');
    });

    if (!text) {
        return res.status(400).json({ error: "No text provided" });
    }

    // Simulate slide generation and return a dummy URL
    const presentationUrl = `http://example.com/presentation/${encodeURIComponent(text)}`;
    res.json({ presentationUrl });
});

ViteExpress.listen(app, 5173, () => console.log("Server + Vite running on port 5173"));