# Recording VCR Cassettes for Energy Tests

## Prerequisites

Your ATA devices must have energy meters. Verify by checking for energy sensor entities in Home Assistant:
- Entity: `sensor.melcloud home_XXXX_XXXX_energy`

## Setup

1. **Set credentials in `.env`:**
   ```bash
   echo "MELCLOUD_EMAIL=your@email.com" >> .env
   echo "MELCLOUD_PASSWORD=yourpassword" >> .env
   source .env
   ```

2. **Verify credentials:**
   ```bash
   echo $MELCLOUD_EMAIL
   ```

## Recording Energy VCR Cassettes

### Step 1: Record Hourly Energy Data

```bash
# Delete existing cassette (if any)
rm -f tests/api/cassettes/TestEnergyDataRetrieval.test_get_energy_data_hourly.yaml

# Run test to record cassette
pytest tests/api/test_energy.py::TestEnergyDataRetrieval::test_get_energy_data_hourly -v

# Verify cassette was created
ls -lh tests/api/cassettes/TestEnergyDataRetrieval.test_get_energy_data_hourly.yaml
```

### Step 2: Record Daily Energy Data

```bash
# Delete existing cassette (if any)
rm -f tests/api/cassettes/TestEnergyDataRetrieval.test_get_energy_data_daily.yaml

# Run test to record cassette
pytest tests/api/test_energy.py::TestEnergyDataRetrieval::test_get_energy_data_daily -v

# Verify cassette was created
ls -lh tests/api/cassettes/TestEnergyDataRetrieval.test_get_energy_data_daily.yaml
```

### Step 3: Verify Recorded Cassettes

```bash
# Run all energy tests (should all pass with cassettes)
pytest tests/api/test_energy.py -v

# Check coverage improvement
pytest tests/api/ --cov=custom_components.melcloudhome.api.client --cov-report=term-missing -q
```

## Expected Results

**After recording cassettes:**
- ✅ 9 energy tests pass (7 already passing + 2 VCR tests)
- ✅ client.py coverage: 68% → ~85% (+17%)
- ✅ API overall coverage: 84% → ~88% (+4%)

## Troubleshooting

### Test Fails with AuthenticationError

**Problem:** `AuthenticationError: User does not exist`

**Solution:** Check your credentials in `.env`:
```bash
cat .env | grep MELCLOUD
```

Ensure credentials are set and source the file:
```bash
source .env
pytest tests/api/test_energy.py::TestEnergyDataRetrieval::test_get_energy_data_hourly -v
```

### Test Skips "No ATA units with energy meters"

**Problem:** Your devices don't have energy meters

**Solution:** You cannot record these cassettes. The parser tests still provide value (parsing.py 100%, client.py parse_energy_response covered).

### Cassette Contains Credentials

**Problem:** VCR cassettes might contain sensitive data

**Solution:** VCR automatically redacts authorization headers. Review cassette before committing:
```bash
grep -i "password\|authorization\|cookie" tests/api/cassettes/TestEnergyDataRetrieval.test_get_energy_data_hourly.yaml
```

Should see `***REDACTED***` or similar for sensitive fields.

## What Gets Tested

**With VCR cassettes:**
1. ✅ Energy endpoint integration (real API contract)
2. ✅ Response parsing with actual API data
3. ✅ Time range parameters (hourly vs daily)
4. ✅ measureData structure validation

**Already tested without VCR:**
1. ✅ parse_energy_response with various inputs
2. ✅ None/empty response handling
3. ✅ Wh → kWh conversion
4. ✅ Authentication requirement check

## Coverage Impact

| File | Before | After Recording | Gain |
|------|--------|----------------|------|
| client.py | 50% | ~85% | +35% |
| API overall | 79% | ~88% | +9% |

## Next Steps

After recording cassettes:
1. Verify all tests pass: `make test`
2. Commit cassettes: `git add tests/api/cassettes/TestEnergyDataRetrieval.*.yaml`
3. Commit test file: `git add tests/api/test_energy.py`
4. Create commit with coverage improvement details
