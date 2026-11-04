import {defineConfig} from '@playwright/test';
import ledger from './playwright.ledger.config';

export default defineConfig(ledger,{
 testMatch:'ledger-observation-gaps.spec.ts',
 use:{baseURL:process.env.E2E_BASE_URL??'http://127.0.0.1:3087'},
});
