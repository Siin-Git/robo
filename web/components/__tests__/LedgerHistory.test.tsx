import {render,screen,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {LedgerHistory} from '../dashboard/LedgerHistory';
vi.mock('@tanstack/react-query',()=>({useQuery:()=>({data:{data_kind:'TEST_FIXTURE',snapshots:[{date:'2026-10-05',nav:100000000,nav_base100:102,cash_balance:1000,cumulative_return:.02,nav_status:'OK',holdings:[]}],orders:[],trades:[]},isLoading:false,isError:false})}));
afterEach(cleanup);
it('distinguishes KRW, base100 index and explicit synthetic source',()=>{render(<LedgerHistory/>);expect(screen.getByText(/검증용 합성 데이터/)).toBeInTheDocument();expect(screen.getByText(/원화 평가액 100,000,000원/)).toBeInTheDocument();expect(screen.getByText(/기준 100 NAV 102.00/)).toBeInTheDocument();expect(screen.queryByText('100,000,000%')).not.toBeInTheDocument();});
