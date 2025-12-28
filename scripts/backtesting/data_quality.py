"""
데이터 품질 검증
"""
import pandas as pd
from typing import Dict, Any


class DataQualityChecker:
    """데이터 품질 검증"""
    
    @staticmethod
    def check_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
        """
        데이터 품질 검사
        
        Returns:
            품질 리포트
        """
        if df.empty:
            return {
                'total_rows': 0,
                'error': 'DataFrame is empty'
            }
        
        report = {
            'total_rows': len(df),
            'date_range': f"{df.index.min()} ~ {df.index.max()}",
            'missing_values': df.isnull().sum().to_dict(),
            'duplicated_index': df.index.duplicated().sum(),
            'negative_values': (df < 0).sum().to_dict(),
            'zero_volume_count': (df['volume'] == 0).sum() if 'volume' in df.columns else 0
        }
        
        # 가격 이상치 감지
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 3 * iqr
                upper_bound = q3 + 3 * iqr
                
                outliers = ((df[col] < lower_bound) | (df[col] > upper_bound)).sum()
                report[f'{col}_outliers'] = outliers
        
        return report
    
    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """데이터 정제"""
        
        if df.empty:
            return df
        
        # 1. 중복 제거
        df = df[~df.index.duplicated(keep='first')]
        
        # 2. 결측치 처리 (forward fill)
        df = df.fillna(method='ffill')
        
        # 3. 음수 값 제거
        for col in df.columns:
            if df[col].min() < 0:
                df = df[df[col] >= 0]
        
        # 4. OHLC 관계 검증
        if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            # High >= Open, Close, Low
            # Low <= Open, Close, High
            valid_mask = (
                (df['high'] >= df['open']) &
                (df['high'] >= df['close']) &
                (df['high'] >= df['low']) &
                (df['low'] <= df['open']) &
                (df['low'] <= df['close']) &
                (df['low'] <= df['high'])
            )
            df = df[valid_mask]
        
        return df
    
    @staticmethod
    def print_quality_report(report: Dict[str, Any]):
        """품질 리포트 출력"""
        print("\n" + "="*60)
        print("데이터 품질 리포트")
        print("="*60)
        for key, value in report.items():
            print(f"  {key}: {value}")
        print("="*60 + "\n")




