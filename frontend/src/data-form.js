import { useState } from 'react';
import {
    Box,
    TextField,
    Button,
} from '@mui/material';
import axios from 'axios';

const endpointMapping = {
    'Notion': 'notion',
    'Airtable': 'airtable',
    'HubSpot': 'hubspot',
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState(null);
    const endpoint = endpointMapping[integrationType];

    const handleLoad = async () => {
        if (!endpoint) {
            console.error("Error: Invalid integration type:", integrationType);
            alert("Invalid integration type. Please select a valid integration.");
            return;
        }
    
        try {
            const formData = new URLSearchParams();
            formData.append("credentials", JSON.stringify(credentials));
    
            const response = await axios.post(
                `http://localhost:8000/integrations/${endpoint}/get_hubspot_items`,
                formData,  
                { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
            );
    
            setLoadedData(response.data);
            console.log("Final Data List from API:", response.data);
    
        } catch (e) {
            console.error("Load Error:", e);
            alert(e?.response?.data?.detail || "Failed to load data.");
        }
    };        

    return (
        <Box display='flex' justifyContent='center' alignItems='center' flexDirection='column' width='100%'>
            <Box display='flex' flexDirection='column' width='100%'>
                <TextField
                    label="Loaded Data"
                    value={loadedData ? JSON.stringify(loadedData, null, 2) : ''}
                    sx={{ mt: 2 }}
                    InputLabelProps={{ shrink: true }}
                    multiline
                    disabled
                />
                <Button
                    onClick={handleLoad}
                    sx={{ mt: 2 }}
                    variant='contained'
                >
                    Load Data
                </Button>
                <Button
                    onClick={() => setLoadedData(null)}
                    sx={{ mt: 1 }}
                    variant='contained'
                >
                    Clear Data
                </Button>
            </Box>
        </Box>
    );
};
