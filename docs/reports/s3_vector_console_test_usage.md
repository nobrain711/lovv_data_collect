# S3 Vector Console Smoke Test Usage

Use this script from AWS CloudShell, PowerShell, or any terminal where AWS CLI v2 supports `s3vectors`.

## Purpose

The smoke test writes one deterministic test vector to `lovv-vector-dev/kr-tour-domain-v1`, queries it back, and deletes it.

It does not use real Lovv content data or embeddings.

## Run

From the project root:

```powershell
python src\kr_vector_index\console_test.py --profile skn26_final
```

For AWS CloudShell, omit `--profile` if the shell already has the target account credentials:

```bash
python src/kr_vector_index/console_test.py
```

## Expected Output

The query result should include:

```text
key: console-test#smoke#0001
```

The script should finish with:

```text
Deleted test vector: console-test#smoke#0001
```

## Keep the Test Vector

Only for manual inspection:

```bash
python src/kr_vector_index/console_test.py --keep-vector
```

If you use `--keep-vector`, delete the vector after inspection:

```bash
aws s3vectors delete-vectors \
  --vector-bucket-name lovv-vector-dev \
  --index-name kr-tour-domain-v1 \
  --keys console-test#smoke#0001 \
  --region us-east-1
```
